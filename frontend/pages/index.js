import { useState, useEffect } from 'react'
import { Card, Typography, Row, Col, Button, Spin, Statistic, Space, Divider, Alert, List } from 'antd'
import { InfoCircleOutlined, GlobalOutlined, DeploymentUnitOutlined, SafetyCertificateOutlined, ArrowRightOutlined } from '@ant-design/icons'
import Link from 'next/link'

const { Title, Paragraph, Text } = Typography

export default function Home() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/stats')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch stats');
        const contentType = res.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          throw new TypeError("Oops, we haven't got JSON!");
        }
        return res.json();
      })
      .then(data => setStats(data))
      .catch(err => console.error("Error fetching stats:", err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ textAlign: 'center', padding: '100px' }}><Spin size="large" tip="Sincronizando con el servidor OAI..." /></div>

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* HERO SECTION */}
      <div style={{ padding: '40px 0', textAlign: 'center' }}>
        <Title level={1} style={{ marginBottom: 16 }}>Open Archives Initiative (OAI-PMH)</Title>
        <Paragraph style={{ fontSize: 20, color: '#666', maxWidth: 800, margin: '0 auto' }}>
          Interoperabilidad para la cosecha masiva de metadatos de la producción científica y académica nacional.
        </Paragraph>
        <div style={{ marginTop: 32 }}>
           <Link href="/records">
             <Button type="primary" size="large" icon={<ArrowRightOutlined />} style={{ height: 50, padding: '0 40px', background: '#328181', borderColor: '#328181' }}>
                Explorar Registros
             </Button>
           </Link>
        </div>
      </div>

      {/* METRICS DASHBOARD */}
      <Row gutter={[24, 24]}>
        <Col xs={24} md={6}>
          <Card bordered={false} className="record-card" style={{ background: '#3b72a1', color: 'white' }}>
            <Statistic 
              title={<span style={{ color: 'rgba(255,255,255,0.8)' }}>Total Registros</span>} 
              value={stats?.total} 
              valueStyle={{ color: 'white', fontWeight: 800, fontSize: 32 }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card bordered={false} className="record-card">
            <Statistic 
              title="Obras Académicas" 
              value={stats?.works} 
              prefix={<DeploymentUnitOutlined />} 
              valueStyle={{ color: '#073b3b' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card bordered={false} className="record-card">
            <Statistic 
              title="Perfiles Investigadores" 
              value={stats?.person} 
              prefix={<SafetyCertificateOutlined />} 
              valueStyle={{ color: '#073b3b' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card bordered={false} className="record-card">
            <Statistic 
              title="Afiliaciones" 
              value={stats?.affiliations} 
              prefix={<GlobalOutlined />} 
              valueStyle={{ color: '#073b3b' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider />

      {/* INFO BLOCKS */}
      <Row gutter={[32, 32]}>
        <Col xs={24} lg={14}>
          <Title level={3}>Propósito del Servidor</Title>
          <Paragraph style={{ fontSize: 16 }}>
            El servidor OAI-PMH de ImpactU expone metadatos estructurados siguiendo los lineamientos de 
            OpenAIRE v4.0 y CERIF. Esto permite que la producción científica de Colombia sea cosechada e indexada 
            por agregadores internacionales, repositorios institucionales y sistemas de información de investigación (CRIS).
          </Paragraph>
          <Alert
            message="Cumplimiento de Estándares"
            description="Este endpoint ha sido validado contra los esquemas oficiales de OAI-PMH v2.0 y el perfil OpenAIRE CERIF v1.2. El prefijo de metadatos soportado es oai_cerif_openaire. Endpoint para cosecha: https://oai.impactu.colav.co/oai"
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
          />
        </Col>

        <Col xs={24} lg={10}>
          <Card title="Endpoints Técnicos">
            <List size="small">
              <List.Item>
                <Text code>verb=Identify</Text> - Info del repositorio
              </List.Item>
              <List.Item>
                <Text code>verb=ListSets</Text> - Colecciones disponibles
              </List.Item>
              <List.Item>
                <Text code>verb=ListMetadataFormats</Text> - Formatos XML
              </List.Item>
              <List.Item>
                <Text code>verb=ListRecords</Text> - Cosecha completa
              </List.Item>
            </List>
            <Button block style={{ marginTop: 16 }} href="/oai?verb=Identify" target="_blank">
               Ver respuesta XML cruda
            </Button>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
