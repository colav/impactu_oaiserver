import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { Card, Button, Typography, Tag, Space, Row, Col, Divider, Spin, Breadcrumb, Tabs } from 'antd'
import { DownloadOutlined, ArrowLeftOutlined, CodeOutlined, FileTextOutlined, GlobalOutlined } from '@ant-design/icons'
import XMLViewer from '../../components/XMLViewer'
import Link from 'next/link'

const { Title, Paragraph, Text } = Typography

export default function RecordDetail() {
  const router = useRouter()
  const { id } = router.query
  const [xml, setXml] = useState(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    const identifier = decodeURIComponent(id)
    const url = `/oai?verb=GetRecord&identifier=${encodeURIComponent(identifier)}&metadataPrefix=oai_cerif_openaire_1.2`
    fetch(url)
      .then(res => res.text())
      .then(t => {
        setXml(t)
        try {
          const doc = new DOMParser().parseFromString(t, 'application/xml')
          const record = doc.getElementsByTagName('record')[0]
          if (record) {
            const md = record.getElementsByTagName('metadata')[0]
            const title = md?.getElementsByTagName('Title')[0]?.textContent || md?.getElementsByTagName('title')[0]?.textContent
            const authors = Array.from(md?.getElementsByTagName('Person') || []).map(p => p.textContent.trim())
            const doi = md?.getElementsByTagName('DOI')[0]?.textContent
            const abstract = md?.getElementsByTagName('Abstract')[0]?.textContent
            const type = md?.getElementsByTagName('Type')[0]?.textContent || 'Publication'
            setData({ title, authors, doi, abstract, type })
          }
        } catch (e) {
          console.error("XML parse error:", e)
        }
      })
      .finally(() => setLoading(false))
  }, [id])

  const downloadXml = () => {
    const blob = new Blob([xml || ''], { type: 'application/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `record-${id}.xml`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  if (loading) return <div style={{ textAlign: 'center', padding: '100px' }}><Spin size="large" tip="Cargando detalles..." /></div>

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 24 }}>
        <Breadcrumb.Item><Link href="/">Inicio</Link></Breadcrumb.Item>
        <Breadcrumb.Item><Link href="/records">Registros</Link></Breadcrumb.Item>
        <Breadcrumb.Item>Detalle del Registro</Breadcrumb.Item>
      </Breadcrumb>

      <Card style={{ marginBottom: 24, borderRadius: 12 }}>
        <Row gutter={[24, 24]}>
          <Col span={24}>
            <Title level={2} style={{ color: '#073b3b', marginBottom: 16 }}>{data?.title || 'Sin título'}</Title>
            <Space wrap size="middle" style={{ marginBottom: 20 }}>
               <Tag color="cyan" style={{ padding: '4px 12px', borderRadius: 6, fontSize: 13 }}>{data?.type}</Tag>
               {data?.doi && <Tag color="orange" style={{ padding: '4px 12px', borderRadius: 6, fontSize: 13 }}>DOI: {data.doi}</Tag>}
            </Space>
            <div style={{ background: '#f9f9f9', padding: '16px 24px', borderRadius: 8, border: '1px solid #f0f0f0' }}>
               <Text strong style={{ color: '#328181', display: 'block', marginBottom: 8 }}>AUTORES:</Text>
               <Text style={{ fontSize: 16 }}>{data?.authors.join(', ') || 'Información no disponible'}</Text>
            </div>
          </Col>

          <Col span={24}>
            <Divider />
            <Title level={4}><FileTextOutlined style={{ marginRight: 8 }} />Resumen</Title>
            <Paragraph style={{ textAlign: 'justify', fontSize: 15, lineHeight: '1.8', color: '#444' }}>
              {data?.abstract || 'Este registro no cuenta con un resumen en los metadatos expuestos.'}
            </Paragraph>
          </Col>

          <Col span={24}>
            <Space size="middle">
              <Button type="primary" icon={<DownloadOutlined />} size="large" onClick={downloadXml} style={{ background: '#328181', borderColor: '#328181' }}>
                Descargar XML
              </Button>
              <Button icon={<ArrowLeftOutlined />} size="large" onClick={() => router.back()}>
                Volver al listado
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card 
        title={<span><CodeOutlined style={{ marginRight: 8 }} /> Metadatos OAI (Fuente XML)</span>}
        style={{ borderRadius: 12 }}
      >
        <XMLViewer xml={xml} />
      </Card>
    </div>
  )
}
