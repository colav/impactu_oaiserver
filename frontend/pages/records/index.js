import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { Card, Typography, List, Space, Tag, Button, Spin, Empty, Pagination, Divider, Row, Col, Menu, Badge } from 'antd'
import { CalendarOutlined, ArrowRightOutlined, DatabaseOutlined, TeamOutlined, FilterOutlined } from '@ant-design/icons'
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
  const { set = 'all', verb = 'ListRecords', query = '' } = router.query
  
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState([])
  const [stats, setStats] = useState({})
  const [resumptionToken, setResumptionToken] = useState(null)

  const parseRecord = (node) => {
    const header = node.getElementsByTagName('header')[0]
    const metadata = node.getElementsByTagName('metadata')[0]
    const identifier = header?.getElementsByTagName('identifier')[0]?.textContent
    const datestamp = header?.getElementsByTagName('datestamp')[0]?.textContent
    
    let title = 'Documento sin título'
    let authors = []
    let type = 'Metadata'

    if (metadata) {
      title = metadata.getElementsByTagName('Title')[0]?.textContent || 
              metadata.getElementsByTagName('title')[0]?.textContent || title
      
      const personNodes = Array.from(metadata.getElementsByTagName('Person') || [])
      authors = personNodes.map(p => p.textContent.trim()).filter(Boolean)
      
      type = metadata.getElementsByTagName('Type')[0]?.textContent || 'Record'
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
    } catch (e) {
      console.error("Stats error:", e)
    }
  }

  const fetchRecords = async (apiUrl) => {
    setLoading(true)
    try {
      const res = await fetch(apiUrl)
      if (!res.ok) throw new Error('OAI server not responding');
      const text = await res.text()
      const parser = new DOMParser()
      const xmlDoc = parser.parseFromString(text, "text/xml")
      
      const rtNodes = xmlDoc.getElementsByTagName('resumptionToken')
      setResumptionToken(rtNodes.length > 0 ? rtNodes[0].textContent : null)

      const recordNodes = Array.from(xmlDoc.getElementsByTagName('record'))
      const parsed = recordNodes.map(parseRecord)
      setRecords(parsed)
    } catch (err) {
      console.error("Fetch error:", err)
      setRecords([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  useEffect(() => {
    if (router.isReady) {
      let url = `/oai?verb=ListRecords&metadataPrefix=oai_cerif_openaire_1.2`
      if (set && set !== 'all') {
        url += `&set=${set}`
      }
      fetchRecords(url)
    }
  }, [router.isReady, set, verb, query])

  const onSetChange = (newSet) => {
    router.push({ pathname: '/records', query: { set: newSet } }, undefined, { shallow: true })
  }

  return (
    <Row gutter={40}>
      {/* SIDEBAR FILTERS */}
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
          <Divider />
          <Card size="small" title="Ayuda" bordered={false} style={{ background: '#f9f9f9' }}>
             <Text type="secondary" style={{ fontSize: 13 }}>
                Este servidor expone la producción científica nacional bajo el protocolo OAI-PMH v2.0.
             </Text>
          </Card>
        </div>
      </Col>

      {/* CONTENT AREA */}
      <Col xs={24} lg={18}>
        <div style={{ marginBottom: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              {OAI_COLLECTIONS.find(c => c.key === set)?.label || 'Explorador'}
            </Title>
            <Text type="secondary">
              Mostrando registros disponibles para el ecosistema de ciencia abierta.
            </Text>
          </div>
          {stats.total && <Tag color="blue">{stats.total} registros totales</Tag>}
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '100px' }}><Spin size="large" tip="Recuperando metadatos..." /></div>
        ) : records.length > 0 ? (
          <>
            <List
              dataSource={records}
              renderItem={item => (
                <Card 
                  className="record-card" 
                  hoverable
                  style={{ marginBottom: 16, cursor: 'default' }}
                  bodyStyle={{ padding: '20px' }}
                >
                  <Row gutter={20} align="top">
                    <Col flex="auto">
                      <Link href={`/records/${encodeURIComponent(item.id)}`}>
                        <Title level={5} style={{ margin: '0 0 8px 0', color: '#073b3b', cursor: 'pointer' }}>
                          {item.title}
                        </Title>
                      </Link>
                      
                      <Space wrap split={<Divider type="vertical" />} style={{ marginBottom: 12 }}>
                        {item.authors.length > 0 ? (
                          item.authors.slice(0, 3).map((a, i) => (
                            <span key={i} style={{ color: '#328181', fontSize: 13, fontWeight: 500 }}>
                              {a}
                            </span>
                          ))
                        ) : <Text type="secondary" italic>Anónimo</Text>}
                        {item.authors.length > 3 && <Text type="secondary" style={{ fontSize: 13 }}>+{item.authors.length - 3} autores</Text>}
                      </Space>

                      <Space size="middle">
                        <Tag color="cyan" style={{ border: 'none' }}>{item.type}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}><CalendarOutlined style={{ marginRight: 4 }} />{item.datestamp}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>ID: {item.id}</Text>
                      </Space>
                    </Col>
                    <Col>
                      <Link href={`/records/${encodeURIComponent(item.id)}`}>
                        <Button type="text" icon={<ArrowRightOutlined />} style={{ color: '#328181' }} />
                      </Link>
                    </Col>
                  </Row>
                </Card>
              )}
            />
            <div style={{ textAlign: 'center', margin: '40px 0' }}>
               <Pagination current={1} total={50} pageSize={10} showSizeChanger={false} />
            </div>
          </>
        ) : (
          <Empty description="No se encontraron registros en esta colección" style={{ marginTop: 100 }} />
        )}
      </Col>
    </Row>
  )
}
