import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { Card, Button, Typography, Tag, Space, Row, Col, Divider, Spin, Breadcrumb, List, Tooltip } from 'antd'
import { DownloadOutlined, ArrowLeftOutlined, CodeOutlined, FileTextOutlined, GlobalOutlined, IdcardOutlined, LinkOutlined } from '@ant-design/icons'
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
    const url = `/oai?verb=GetRecord&identifier=${encodeURIComponent(identifier)}&metadataPrefix=oai_cerif_openaire`
    fetch(url)
      .then(res => res.text())
      .then(t => {
        setXml(t)
        try {
          const doc = new DOMParser().parseFromString(t, 'application/xml')
          const record = doc.getElementsByTagName('record')[0]
          if (record) {
            const md = record.getElementsByTagName('metadata')[0]?.firstElementChild
            if (!md) return;

            const type = md.tagName;
            let title = 'Sin título';
            let extra = {};

            if (type === 'Person') {
              const family = md.getElementsByTagName('FamilyNames')[0]?.textContent || '';
              const first = md.getElementsByTagName('FirstNames')[0]?.textContent || '';
              title = `${family}, ${first}`.trim();
              extra.orcid = md.getElementsByTagName('ORCID')[0]?.textContent;
              extra.scopus = md.getElementsByTagName('ScopusAuthorID')[0]?.textContent;
            } else if (type === 'OrgUnit') {
              title = md.getElementsByTagName('Name')[0]?.textContent || '';
              extra.ror = md.getElementsByTagName('RORID')[0]?.textContent;
            } else {
              title = md.getElementsByTagName('Title')[0]?.textContent || md.getElementsByTagName('title')[0]?.textContent || '';
              extra.doi = md.getElementsByTagName('DOI')[0]?.textContent;
              extra.abstract = md.getElementsByTagName('Abstract')[0]?.textContent;
              
              const personNodes = Array.from(md.getElementsByTagName('Person') || [])
              extra.authors = personNodes.map(p => {
                const f = p.getElementsByTagName('FamilyNames')[0]?.textContent || '';
                const n = p.getElementsByTagName('FirstNames')[0]?.textContent || '';
                return f || n ? `${f}, ${n}` : p.textContent.trim();
              }).filter(Boolean);
            }
            
            setData({ title, type, ...extra })
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

  if (loading) return <div style={{ textAlign: 'center', padding: '100px' }}><Spin size="large" /></div>

  return (
    <div>
      <Breadcrumb style={{ marginBottom: 24 }}>
        <Breadcrumb.Item><Link href="/">Inicio</Link></Breadcrumb.Item>
        <Breadcrumb.Item><Link href="/records">Registros</Link></Breadcrumb.Item>
        <Breadcrumb.Item>Detalle</Breadcrumb.Item>
      </Breadcrumb>

      <Card style={{ marginBottom: 24, borderRadius: 12 }}>
        <Row gutter={[24, 24]}>
          <Col span={24}>
            <Title level={2} style={{ color: '#073b3b', marginBottom: 16 }}>{data?.title || 'Sin Título'}</Title>
            <Space wrap size="middle" style={{ marginBottom: 20 }}>
               <Tag color="cyan" style={{ padding: '4px 12px', borderRadius: 6 }}>{data?.type}</Tag>
               {data?.doi && <Tag color="orange">DOI: {data.doi}</Tag>}
               {data?.orcid && <Tag color="green">ORCID: {data.orcid}</Tag>}
               {data?.ror && <Tag color="blue">ROR: {data.ror}</Tag>}
            </Space>
            
            {data?.type === 'Person' ? (
              <div style={{ background: '#f9f9f9', padding: '24px', borderRadius: 8, border: '1px solid #f0f0f0' }}>
                 <Title level={4}><IdcardOutlined /> Información del Perfil</Title>
                 <List size="small">
                    <List.Item><b>Identificador OAI:</b> <Text code>{id}</Text></List.Item>
                    {data.orcid && <List.Item><b>ORCID:</b> <a href={`https://orcid.org/${data.orcid}`} target="_blank" rel="noreferrer">{data.orcid}</a></List.Item>}
                    {data.scopus && <List.Item><b>Scopus ID:</b> {data.scopus}</List.Item>}
                 </List>
              </div>
            ) : data?.authors?.length > 0 && (
              <div style={{ background: '#f9f9f9', padding: '16px 24px', borderRadius: 8, border: '1px solid #f0f0f0' }}>
                <Text strong style={{ color: '#328181', display: 'block', marginBottom: 8 }}>AUTORES:</Text>
                <Text style={{ fontSize: 16 }}>{data.authors.join('; ')}</Text>
              </div>
            )}
          </Col>

          {data?.abstract && (
            <Col span={24}>
              <Divider />
              <Title level={4}><FileTextOutlined style={{ marginRight: 8 }} />Resumen</Title>
              <Paragraph style={{ textAlign: 'justify', fontSize: 15, lineHeight: '1.8' }}>
                {data.abstract}
              </Paragraph>
            </Col>
          )}

          <Col span={24}>
            <Divider />
            <Space size="middle">
              <Button type="primary" icon={<DownloadOutlined />} size="large" onClick={downloadXml} style={{ background: '#328181', borderColor: '#328181' }}>
                Descargar XML
              </Button>
              <Button icon={<ArrowLeftOutlined />} size="large" onClick={() => router.back()}>
                Volver
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card 
        title={<span><CodeOutlined style={{ marginRight: 8 }} /> Metadatos OAI (CERIF XML)</span>}
        style={{ borderRadius: 12 }}
      >
        <XMLViewer xml={xml} />
      </Card>
    </div>
  )
}
