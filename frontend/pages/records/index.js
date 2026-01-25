import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { Card, Typography, List, Space, Tag, Button, Spin, Empty, Pagination, Divider, Row, Col, Menu, Badge } from 'antd'
import { CalendarOutlined, ArrowRightOutlined, DatabaseOutlined, TeamOutlined, FilterOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import Link from 'next/link'

const { Title, Text } = Typography

const OAI_COLLECTIONS = [
  { key: 'all', label: 'Todos los Registros', icon: <DatabaseOutlined /> },
  { key: 'works', label: 'Obras (Works)', countKey: 'works' },
  { key: 'person', label: 'Personas', countKey: 'person' },
  { key: 'affiliations', label: 'Afiliaciones', countKey: 'affiliations' },
  { key: 'projects', label: 'Proyectos', countKey: 'projects' },
  { key: 'patents', label: 'Patentes', countKey: 'patents' },
  { key: 'sources', label: 'Fuentes', countKey: 'sources' },
  { key: 'events', label: 'Eventos', countKey: 'events' },
  { key: 'subjects', label: 'Temas', countKey: 'subjects' },
]

export default function Records() {
  const router = useRouter()
  const { set = 'all' } = router.query
  
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState([])
  const [stats, setStats] = useState({})
  
  // Pagination / OAI state
  const [resumptionToken, setResumptionToken] = useState(null)
  const [historyTokens, setHistoryTokens] = useState([]) // To allow "back" navigation
  const [totalCount, setTotalCount] = useState(0)
  const [cursor, setCursor] = useState(0)

  const parseRecord = (node) => {
    const header = node.getElementsByTagName('header')[0]
    const metadata = node.getElementsByTagName('metadata')[0]
    const identifier = header?.getElementsByTagName('identifier')[0]?.textContent
    const datestamp = header?.getElementsByTagName('datestamp')[0]?.textContent
    
    let title = 'Sin título/nombre'
    let authors = []
    let type = 'Registro'

    if (metadata) {
      // Try to find the root entity (Person, Publication, OrgUnit, Project, etc)
      const root = metadata.firstElementChild;
      if (root) {
        type = root.tagName;
        
        // 1. PERSON: Name = FamilyNames + FirstNames
        if (type === 'Person') {
          const family = root.getElementsByTagName('FamilyNames')[0]?.textContent || '';
          const first = root.getElementsByTagName('FirstNames')[0]?.textContent || '';
          title = \`\${family}\${family && first ? ', ' : ''}\${first}\`.trim() || identifier;
        } 
        // 2. ORGUNIT: Name
        else if (type === 'OrgUnit') {
          title = root.getElementsByTagName('Name')[0]?.textContent || identifier;
        }
        // 3. PUBLICATION / OTHER: Title
        else {
          title = root.getElementsByTagName('Title')[0]?.textContent || 
                  root.getElementsByTagName('title')[0]?.textContent || 
                  root.getElementsByTagName('Name')[0]?.textContent ||
                  identifier;
        }

        // Extract authors (works for Publications)
        const personNodes = Array.from(root.getElementsByTagName('Person') || [])
        authors = personNodes.map(p => {
          const f = p.getElementsByTagName('FamilyNames')[0]?.textContent || '';
          const n = p.getElementsByTagName('FirstNames')[0]?.textContent || '';
          return f || n ? \`\${f}, \${n}\` : p.textContent.trim();
        }).filter(Boolean)
      }
    }

    return { id: identifier, title, authors, datestamp, type }
  }

  const fetchStats = async () => {
    try {
      const res = await fetch('/stats')
      if (!res.ok) return;
      const contentType = res.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await res.json()
        setStats(data)
      }
    } catch (e) { console.error(e) }
  }

  const fetchRecords = async (url) => {
    setLoading(true)
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error('OAI server error')
      const text = await res.text()
      const parser = new DOMParser()
      const xmlDoc = parser.parseFromString(text, "text/xml")
      
      const rtNode = xmlDoc.getElementsByTagName('resumptionToken')[0]
      if (rtNode) {
        setResumptionToken(rtNode.textContent || null)
        setTotalCount(parseInt(rtNode.getAttribute('completeListSize') || '0'))
        setCursor(parseInt(rtNode.getAttribute('cursor') || '0'))
      } else {
        setResumptionToken(null)
      }

      const recordNodes = Array.from(xmlDoc.getElementsByTagName('record'))
      setRecords(recordNodes.map(parseRecord))
    } catch (err) {
      console.error(err)
      setRecords([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchStats() }, [])

  useEffect(() => {
    if (router.isReady) {
      // RESET pagination when collection changes
      setHistoryTokens([])
      let url = `/oai?verb=ListRecords&metadataPrefix=oai_cerif_openaire_1.2`
      if (set && set !== 'all') url += `&set=${set}`
      fetchRecords(url)
    }
  }, [router.isReady, set])

  const goNext = () => {
    if (!resumptionToken) return
    setHistoryTokens([...historyTokens, resumptionToken]) // This is simplistic but OAI is sequential
    fetchRecords(`/oai?verb=ListRecords&resumptionToken=${encodeURIComponent(resumptionToken)}`)
  }

  const onSetChange = (newSet) => {
    router.push({ pathname: '/records', query: { set: newSet } }, undefined, { shallow: true })
  }

  return (
    <Row gutter={40}>
      <Col xs={24} lg={6}>
        <div style={{ position: 'sticky', top: 120 }}>
          <Title level={4} style={{ marginBottom: 24 }}><FilterOutlined /> Colecciones</Title>
          <Menu
            mode="vertical"
            selectedKeys={[set]}
            style={{ border: 'none', background: 'transparent' }}
            items={OAI_COLLECTIONS.map(item => ({
              key: item.key,
              label: (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{item.icon} {item.label}</span>
                  {item.countKey && stats[item.countKey] !== undefined && (
                    <Badge count={stats[item.countKey]} overflowCount={99999} style={{ backgroundColor: '#e6f7ff', color: '#1890ff', boxShadow: 'none' }} />
                  )}
                </div>
              ),
              onClick: () => onSetChange(item.key)
            }))}
          />
        </div>
      </Col>

      <Col xs={24} lg={18}>
        <div style={{ marginBottom: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {OAI_COLLECTIONS.find(c => c.key === set)?.label || 'Explorador'}
            </Title>
            <Text type="secondary">
              {(totalCount > 0) ? `Mostrando desde el registro ${cursor + 1} de ${totalCount}` : 'Cargando registros...'}
            </Text>
          </div>
          <Space>
             {stats.total && <Tag color="blue">{stats.total} total global</Tag>}
          </Space>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '100px' }}><Spin size="large" /></div>
        ) : records.length > 0 ? (
          <>
            <List
              dataSource={records}
              renderItem={item => (
                <Card className="record-card" hoverable style={{ marginBottom: 16 }} bodyStyle={{ padding: '20px' }}>
                  <Row gutter={20} align="top">
                    <Col flex="auto">
                      <Link href={`/records/${encodeURIComponent(item.id)}`}>
                        <Title level={5} style={{ margin: '0 0 8px 0', color: '#073b3b', cursor: 'pointer' }}>{item.title}</Title>
                      </Link>
                      <Space wrap split={<Divider type="vertical" />} style={{ marginBottom: 12 }}>
                        {item.authors.length > 0 ? item.authors.slice(0, 3).map((a, i) => (
                          <span key={i} style={{ color: '#328181', fontSize: 13, fontWeight: 500 }}>{a}</span>
                        )) : <Text type="secondary" italic>Anónimo</Text>}
                      </Space>
                      <Space size="middle">
                        <Tag color="cyan">{item.type}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}><CalendarOutlined /> {item.datestamp}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>ID: {item.id}</Text>
                      </Space>
                    </Col>
                    <Col><Link href={`/records/${encodeURIComponent(item.id)}`}><Button type="text" icon={<ArrowRightOutlined />} /></Link></Col>
                  </Row>
                </Card>
              )}
            />
            
            <div style={{ textAlign: 'center', marginTop: 40, paddingBottom: 40 }}>
               <Space size="large">
                  <Button 
                    disabled={cursor === 0} 
                    icon={<ArrowLeftOutlined />}
                    onClick={() => router.reload()} // OAI reverse pagination is hard, usually simpler to reload or track tokens better
                  >
                    Primera Página
                  </Button>
                  <Button 
                    type="primary" 
                    icon={<ArrowRightOutlined />} 
                    disabled={!resumptionToken}
                    onClick={goNext}
                    style={{ background: '#328181', borderColor: '#328181' }}
                  >
                    Siguiente Página
                  </Button>
               </Space>
            </div>
          </>
        ) : <Empty style={{ marginTop: 100 }} />}
      </Col>
    </Row>
  )
}
