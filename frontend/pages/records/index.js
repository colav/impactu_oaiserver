import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { 
  Card, Typography, List, Space, Tag, Button, Spin, Empty, 
  Divider, Row, Col, Menu, Badge, Tooltip, Select, DatePicker, 
  Input, Skeleton, Progress
} from 'antd'
import { 
  CalendarOutlined, ArrowRightOutlined, DatabaseOutlined, 
  FilterOutlined, ArrowLeftOutlined, DownloadOutlined,
  SearchOutlined, SettingOutlined, CodeOutlined,
  DeleteOutlined, SortAscendingOutlined, FileTextOutlined,
  FileZipOutlined, TeamOutlined, DeploymentUnitOutlined,
  ProjectOutlined, SafetyCertificateOutlined, WarningOutlined
} from '@ant-design/icons'
import Link from 'next/link'
import dayjs from 'dayjs'
import { Alert } from 'antd'

const { Title, Text, Paragraph } = Typography
const { Option } = Select
const { RangePicker } = DatePicker

const OAI_COLLECTIONS = [
  { key: 'all', label: 'Todos los Registros', icon: <DatabaseOutlined />, countKey: 'total' },
  { key: 'openaire_cris_publications', label: 'Publicaciones', countKey: 'works', icon: <FileTextOutlined /> },
  { key: 'openaire_cris_persons', label: 'Investigadores', countKey: 'person', icon: <TeamOutlined /> },
  { key: 'openaire_cris_orgunits', label: 'Organizaciones', countKey: 'affiliations', icon: <DeploymentUnitOutlined /> },
  { key: 'openaire_cris_projects', label: 'Proyectos', countKey: 'projects', icon: <ProjectOutlined /> },
  { key: 'openaire_cris_products', label: 'Productos/Fuentes', countKey: 'sources', icon: <DatabaseOutlined /> },
  { key: 'openaire_cris_patents', label: 'Patentes', countKey: 'patents', icon: <SafetyCertificateOutlined /> },
  { key: 'openaire_cris_events', label: 'Eventos', countKey: 'events', icon: <CalendarOutlined /> },
]

const METADATA_FORMATS = [
  { value: 'oai_cerif_openaire_1.2', label: 'CERIF OpenAIRE 1.2', description: 'Formato estándar OpenAIRE CRIS 1.2' },
  { value: 'oai_cerif_openaire_1.1.1', label: 'CERIF OpenAIRE 1.1.1', description: 'Versión compatible 1.1.1' },
]

export default function Records() {
  const router = useRouter()
  const { set = 'all', prefix = 'oai_cerif_openaire_1.2', from, until } = router.query
  
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState([])
  const [stats, setStats] = useState({})
  const [localSearch, setLocalSearch] = useState('')
  const [sortOrder, setSortOrder] = useState('newest') // newest, oldest, title
  
  // Pagination / OAI state
  const [resumptionToken, setResumptionToken] = useState(null)
  const [totalCount, setTotalCount] = useState(0)
  const [cursor, setCursor] = useState(0)

  const parseRecord = (node) => {
    // Helper to find child by local name (case-insensitive and namespace-agnostic)
    const getLocal = (parent, name) => {
      if (!parent) return null;
      const lowerReq = name.toLowerCase();
      return Array.from(parent.childNodes).find(n => 
        n.nodeType === 1 && (n.localName?.toLowerCase() === lowerReq || n.nodeName.split(':').pop().toLowerCase() === lowerReq)
      );
    };

    const getAllLocal = (parent, name) => {
      if (!parent) return [];
      const lowerReq = name.toLowerCase();
      return Array.from(parent.childNodes).filter(n => 
        n.nodeType === 1 && (n.localName?.toLowerCase() === lowerReq || n.nodeName.split(':').pop().toLowerCase() === lowerReq)
      );
    };

    const header = getLocal(node, 'header');
    const metadata = getLocal(node, 'metadata');
    const identifier = getLocal(header, 'identifier')?.textContent || 'Sin ID';
    const datestamp = getLocal(header, 'datestamp')?.textContent || '-';
    
    let title = 'Sin título/nombre'
    let authors = []
    let type = 'Registro'
    let description = ''

    if (metadata) {
      // The entity (Publication, Person, etc.) is the first ELEMENT node inside metadata
      const root = Array.from(metadata.childNodes).find(n => n.nodeType === 1);
      
      if (root) {
        type = root.localName || root.nodeName.split(':').pop();
        
        if (type === 'Person') {
          const family = getLocal(root, 'FamilyNames')?.textContent || '';
          const first = getLocal(root, 'FirstNames')?.textContent || '';
          title = `${family}${family && first ? ', ' : ''}${first}`.trim() || identifier;
        } 
        else if (type === 'OrgUnit') {
          title = getLocal(root, 'Name')?.textContent || identifier;
        }
        else {
          title = getLocal(root, 'Title')?.textContent || 
                  getLocal(root, 'title')?.textContent || 
                  getLocal(root, 'Name')?.textContent ||
                  identifier;
          description = getLocal(root, 'Abstract')?.textContent || '';
        }

        authors = getAllLocal(root, 'Person').map(p => {
          const f = getLocal(p, 'FamilyNames')?.textContent || '';
          const n = getLocal(p, 'FirstNames')?.textContent || '';
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

  const [errorHeader, setErrorHeader] = useState(null)

  const fetchRecords = async (url) => {
    setLoading(true)
    setErrorHeader(null)
    setRecords([]) // Clear existing records to avoid confusion
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`)
      const text = await res.text()
      const parser = new DOMParser()
      const xmlDoc = parser.parseFromString(text, "text/xml")
      
      // Check for XML parsing error
      const parserError = xmlDoc.getElementsByTagName("parsererror")[0];
      if (parserError) {
        console.error("XML Parser Error:", parserError.textContent);
        throw new Error("Error al procesar la respuesta XML del servidor OAI");
      }

      const findInDoc = (tagName) => {
        const lower = tagName.toLowerCase();
        return Array.from(xmlDoc.getElementsByTagName('*')).filter(n => 
          (n.localName?.toLowerCase() === lower || n.nodeName.split(':').pop().toLowerCase() === lower)
        );
      };

      const oaiError = findInDoc('error')[0];
      if (oaiError) {
        setErrorHeader({
          code: oaiError.getAttribute('code') || 'Error',
          message: oaiError.textContent
        })
        setTotalCount(0)
        return
      }

      const rtNode = findInDoc('resumptionToken')[0];
      if (rtNode) {
        setResumptionToken(rtNode.textContent?.trim() || null)
        setTotalCount(parseInt(rtNode.getAttribute('completeListSize') || '0'))
        setCursor(parseInt(rtNode.getAttribute('cursor') || '0'))
      } else {
        setResumptionToken(null)
        setTotalCount(0)
      }

      const recordNodes = findInDoc('record');
      console.log(`Found ${recordNodes.length} records`);
      setRecords(recordNodes.map(parseRecord))
    } catch (err) {
      console.error('OAI Fetch Error:', err)
      setErrorHeader({ code: 'Error de Red/Formato', message: err.message })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchStats() }, [])

  useEffect(() => {
    if (router.isReady) {
      const { set, prefix, from, until } = router.query
      const pref = prefix || 'oai_cerif_openaire_1.2'
      let url = `/oai?verb=ListRecords&metadataPrefix=${pref}`
      if (set && set !== 'all') url += `&set=${set}`
      if (from) url += `&from=${from}`
      if (until) url += `&until=${until}`
      fetchRecords(url)
    }
  }, [router.isReady, router.query.set, router.query.prefix, router.query.from, router.query.until])

  const onParamChange = (key, value) => {
    router.push({ 
      pathname: '/records', 
      query: { ...router.query, [key]: value } 
    }, undefined, { shallow: true })
  }

  const resetFilters = () => {
    router.push('/records')
    setLocalSearch('')
  }

  const exportData = (format) => {
    const data = filteredRecords.map(r => ({
      id: r.id,
      title: r.title,
      type: r.type,
      datestamp: r.datestamp,
      authors: r.authors.join('; ')
    }))

    if (format === 'json') {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `records_${set}.json`
      a.click()
    } else if (format === 'csv') {
      const headers = ['ID', 'Title', 'Type', 'Datestamp', 'Authors']
      const csv = [
        headers.join(','),
        ...data.map(r => [
          `"${r.id}"`, `"${r.title.replace(/"/g, '""')}"`, `"${r.type}"`, `"${r.datestamp}"`, `"${r.authors.replace(/"/g, '""')}"`
        ].join(','))
      ].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `records_${set}.csv`
      a.click()
    }
  }

  const sortedRecords = [...records].sort((a, b) => {
    if (sortOrder === 'newest') return new Date(b.datestamp) - new Date(a.datestamp)
    if (sortOrder === 'oldest') return new Date(a.datestamp) - new Date(b.datestamp)
    if (sortOrder === 'title') return a.title.localeCompare(b.title)
    return 0
  })

  const filteredRecords = sortedRecords.filter(r => 
    r.title.toLowerCase().includes(localSearch.toLowerCase()) || 
    r.id.toLowerCase().includes(localSearch.toLowerCase())
  )

  return (
    <Row gutter={40}>
      <Col xs={24} lg={6}>
        <div style={{ position: 'sticky', top: 120 }}>
          <Card size="small" style={{ marginBottom: 24, borderRadius: 12, border: '1px solid #e1e9e9' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Title level={5} style={{ margin: 0 }}><SettingOutlined /> OAI Params</Title>
              <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={resetFilters}>Limpiar</Button>
            </div>
            <Divider style={{ margin: '12px 0' }} />
            
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <Text strong style={{ fontSize: 12 }}>Metadata Prefix:</Text>
              <Select 
                value={prefix} 
                style={{ width: '100%' }} 
                onChange={(v) => onParamChange('prefix', v)}
              >
                {METADATA_FORMATS.map(f => <Option key={f.value} value={f.value}>{f.label}</Option>)}
              </Select>

              <Text strong style={{ fontSize: 12, marginTop: 12 }}>Rango de Cosecha (Date):</Text>
              <RangePicker 
                style={{ width: '100%' }} 
                value={from && until ? [dayjs(from), dayjs(until)] : null}
                onChange={(dates) => {
                  if (dates) {
                    onParamChange('from', dates[0].format('YYYY-MM-DD'))
                    onParamChange('until', dates[1].format('YYYY-MM-DD'))
                  } else {
                    const newQuery = { ...router.query }
                    delete newQuery.from
                    delete newQuery.until
                    router.push({ pathname: '/records', query: newQuery }, undefined, { shallow: true })
                  }
                }}
              />
              
              <Text strong style={{ fontSize: 12, marginTop: 12 }}>Ordenar resultados:</Text>
              <Select 
                value={sortOrder} 
                style={{ width: '100%' }} 
                onChange={setSortOrder}
                suffixIcon={<SortAscendingOutlined />}
              >
                <Option value="newest">Más recientes primero</Option>
                <Option value="oldest">Más antiguos primero</Option>
                <Option value="title">Por título (A-Z)</Option>
              </Select>
            </Space>
          </Card>

          <Title level={5} style={{ marginBottom: 16 }}><FilterOutlined /> Colecciones OAI</Title>
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
                    <Badge 
                      count={stats[item.countKey]} 
                      overflowCount={99999999} 
                      style={{ backgroundColor: '#e6f7ff', color: '#1890ff', boxShadow: 'none' }} 
                    />
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
                {loading ? 'Consultando servidor OAI...' : 
                 errorHeader ? `Error: ${errorHeader.code}` :
                 (totalCount > 0) ? `Mostrando registros ${cursor + 1} - ${cursor + filteredRecords.length} de ${totalCount}` : 
                 'No hay registros para mostrar'}
              </Text>
              {totalCount > 0 && !loading && (
                <Progress 
                  percent={Math.round((cursor + filteredRecords.length) / totalCount * 100)} 
                  size="small" 
                  status="active" 
                  strokeColor="#328181"
                  style={{ width: 220, display: 'block', marginTop: 4 }}
                />
              )}
            </Col>
            <Col>
              <Space wrap>
                <Input 
                   placeholder="Filtrar en esta página..." 
                   prefix={<SearchOutlined />} 
                   value={localSearch}
                   onChange={e => setLocalSearch(e.target.value)}
                   style={{ width: 220 }}
                />
                <Tooltip title="Descargar vista actual como CSV">
                  <Button icon={<FileTextOutlined />} onClick={() => exportData('csv')} />
                </Tooltip>
                <Tooltip title="Link de cosecha OAI-PMH (XML)">
                  <Button 
                    type="primary"
                    icon={<DownloadOutlined />} 
                    href={`/oai?verb=ListRecords&metadataPrefix=${prefix}${set !== 'all' ? `&set=${set}` : ''}${from ? `&from=${from}`:''}${until?`&until=${until}`:''}`}
                    target="_blank"
                    style={{ background: '#328181', borderColor: '#328181' }}
                  >
                    XML
                  </Button>
                </Tooltip>
              </Space>
            </Col>
          </Row>
        </div>

        {errorHeader && (
          <Alert
            message={`Error OAI: ${errorHeader.code}`}
            description={errorHeader.message}
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            style={{ marginBottom: 24, borderRadius: 8 }}
          />
        )}

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
                        <Tooltip title="Copiar ID">
                           <Button 
                             size="small" 
                             type="text" 
                             icon={<CodeOutlined style={{ fontSize: 12 }} />} 
                             onClick={(e) => {
                               e.stopPropagation();
                               navigator.clipboard.writeText(item.id);
                             }} 
                           />
                        </Tooltip>
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
