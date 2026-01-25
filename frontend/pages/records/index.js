import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { 
  Card, Typography, List, Space, Tag, Button, Spin, Empty, 
  Divider, Row, Col, Menu, Badge, Tooltip, Select, DatePicker, 
  Input, Skeleton 
} from 'antd'
import { 
  CalendarOutlined, ArrowRightOutlined, DatabaseOutlined, 
  FilterOutlined, ArrowLeftOutlined, DownloadOutlined,
  SearchOutlined, SettingOutlined
} from '@ant-design/icons'
import Link from 'next/link'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { Option } = Select
const { RangePicker } = DatePicker

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

const METADATA_FORMATS = [
  { value: 'oai_cerif_openaire_1.2', label: 'CERIF OpenAIRE 1.2' },
  { value: 'oai_cerif_openaire_1.1.1', label: 'CERIF OpenAIRE 1.1.1' },
]

export default function Records() {
  const router = useRouter()
  const { set = 'all', prefix = 'oai_cerif_openaire_1.2' } = router.query
  
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState([])
  const [stats, setStats] = useState({})
  const [localSearch, setLocalSearch] = useState('')
  
  // Pagination / OAI state
  const [resumptionToken, setResumptionToken] = useState(null)
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
    let description = ''

    if (metadata) {
      const root = metadata.firstElementChild;
      if (root) {
        type = root.tagName;
        if (type === 'Person') {
          const family = root.getElementsByTagName('FamilyNames')[0]?.textContent || '';
          const first = root.getElementsByTagName('FirstNames')[0]?.textContent || '';
          title = `${family}${family && first ? ', ' : ''}${first}`.trim() || identifier;
        } 
        else if (type === 'OrgUnit') {
          title = root.getElementsByTagName('Name')[0]?.textContent || identifier;
        }
        else {
          title = root.getElementsByTagName('Title')[0]?.textContent || 
                  root.getElementsByTagName('title')[0]?.textContent || 
                  root.getElementsByTagName('Name')[0]?.textContent ||
                  identifier;
          description = root.getElementsByTagName('Abstract')[0]?.textContent || '';
        }

        const personNodes = Array.from(root.getElementsByTagName('Person') || [])
        authors = personNodes.map(p => {
          const f = p.getElementsByTagName('FamilyNames')[0]?.textContent || '';
          const n = p.getElementsByTagName('FirstNames')[0]?.textContent || '';
          return f || n ? `${f}, ${n}` : p.textContent.trim();
        }).filter(Boolean)
      }
    }

    return { id: identifier, title, authors, datestamp, type, description }
  }

  const fetchStats = async () => {
    try {
      const res = await fetch('/stats')
      if (res.ok) {
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
      let url = `/oai?verb=ListRecords&metadataPrefix=${prefix}`
      if (set && set !== 'all') url += `&set=${set}`
      fetchRecords(url)
    }
  }, [router.isReady, set, prefix])

  const onParamChange = (key, value) => {
    router.push({ 
      pathname: '/records', 
      query: { ...router.query, [key]: value } 
    }, undefined, { shallow: true })
  }

  const filteredRecords = records.filter(r => 
    r.title.toLowerCase().includes(localSearch.toLowerCase()) || 
    r.id.toLowerCase().includes(localSearch.toLowerCase())
  )

  return (
    <Row gutter={40}>
      <Col xs={24} lg={6}>
        <div style={{ position: 'sticky', top: 120 }}>
          <Card size="small" style={{ marginBottom: 24, borderRadius: 8 }}>
            <Title level={5}><SettingOutlined /> Configuración OAI</Title>
            <Divider style={{ margin: '12px 0' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>Metadata Prefix:</Text>
            <Select 
              value={prefix} 
              style={{ width: '100%', marginTop: 8 }} 
              onChange={(v) => onParamChange('prefix', v)}
            >
              {METADATA_FORMATS.map(f => <Option key={f.value} value={f.value}>{f.label}</Option>)}
            </Select>
          </Card>

          <Title level={5} style={{ marginBottom: 16 }}><FilterOutlined /> Colecciones</Title>
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
              onClick: () => onParamChange('set', item.key)
            }))}
          />
        </div>
      </Col>

      <Col xs={24} lg={18}>
        <div style={{ marginBottom: 32 }}>
          <Row justify="space-between" align="bottom">
            <Col>
              <Title level={3} style={{ margin: 0 }}>
                {OAI_COLLECTIONS.find(c => c.key === set)?.label || 'Explorador'}
              </Title>
              <Text type="secondary">
                {(totalCount > 0) ? `Mostrando desde el registro ${cursor + 1} de ${totalCount}` : 'Explorando metadatos...'}
              </Text>
            </Col>
            <Col>
              <Space>
                <Input 
                   placeholder="Filtrar en esta página..." 
                   prefix={<SearchOutlined />} 
                   value={localSearch}
                   onChange={e => setLocalSearch(e.target.value)}
                   style={{ width: 250 }}
                />
                <Tooltip title="Obtener link de cosecha OAI-PMH">
                  <Button 
                    icon={<DownloadOutlined />} 
                    href={`/oai?verb=ListRecords&metadataPrefix=${prefix}${\"&set=\" + set}`}
                    target="_blank"
                  />
                </Tooltip>
              </Space>
            </Col>
          </Row>
        </div>

        {loading ? (
          <List
            grid={{ gutter: 16, column: 1 }}
            dataSource={[1, 2, 3, 4]}
            renderItem={() => (
              <Card style={{ marginBottom: 16 }}>
                <Skeleton active avatar={{ size: 'large' }} paragraph={{ rows: 2 }} />
              </Card>
            )}
          />
        ) : filteredRecords.length > 0 ? (
          <>
            <List
              dataSource={filteredRecords}
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
                        )) : <Text type="secondary" italic>Información no disponible</Text>}
                      </Space>
                      {item.description && (
                        <Paragraph ellipsis={{ rows: 2 }} style={{ color: '#666', fontSize: 13 }}>
                          {item.description}
                        </Paragraph>
                      )}
                      <Space size="middle">
                        <Tag color="cyan">{item.type}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}><CalendarOutlined /> {item.datestamp}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>{item.id}</Text>
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
                  onClick={() => onParamChange('set', set)} // Reset
                >
                  Inicio
                </Button>
                <Button 
                  type="primary" 
                  icon={<ArrowRightOutlined />} 
                  disabled={!resumptionToken}
                  onClick={() => fetchRecords(`/oai?verb=ListRecords&resumptionToken=${encodeURIComponent(resumptionToken)}`)}
                  style={{ background: '#328181', borderColor: '#328181' }}
                >
                  Siguiente Página
                </Button>
              </Space>
            </div>
          </>
        ) : <Empty description="No se encontraron registros en esta página" style={{ marginTop: 100 }} />}
      </Col>
    </Row>
  )
}
