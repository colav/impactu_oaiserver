import React, { useState } from 'react'
import { Layout, Card, Input, Button, Table, Space, Typography, Tag } from 'antd'
import XMLViewer from '../../components/XMLViewer'

const { Header, Content, Footer } = Layout
const { Title } = Typography

export default function Records() {
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState([])
  const [selectedXml, setSelectedXml] = useState(null)
  const [query, setQuery] = useState('verb=ListRecords&metadataPrefix=oai_cerif_openaire_1.2&pageSize=10')

  async function fetchRecords() {
    setLoading(true)
    try {
      const url = '/oai?' + query
      const res = await fetch(url)
      const text = await res.text()
      const doc = new DOMParser().parseFromString(text, 'application/xml')
      const recs = Array.from(doc.getElementsByTagName('record')).map((r) => {
        const header = r.getElementsByTagName('header')[0]
        const ident = header?.getElementsByTagName('identifier')[0]?.textContent || ''
        const datestamp = header?.getElementsByTagName('datestamp')[0]?.textContent || ''
        // find first meaningful metadata child name
        let entity = ''
        const md = r.getElementsByTagName('metadata')[0]
        if (md && md.firstElementChild) entity = md.firstElementChild.localName
        return { key: ident + '|' + datestamp, ident, datestamp, entity, raw: new XMLSerializer().serializeToString(r) }
      })
      setRecords(recs)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: 'Identifier', dataIndex: 'ident', key: 'ident', render: (t) => <code>{t}</code> },
    { title: 'Date', dataIndex: 'datestamp', key: 'datestamp' },
    { title: 'Entity', dataIndex: 'entity', key: 'entity', render: (t) => <Tag color="blue">{t || 'Unknown'}</Tag> },
    {
      title: 'Actions', key: 'actions', render: (_, rec) => (
        <Space>
          <Button onClick={() => setSelectedXml(rec.raw)}>View XML</Button>
          <Button onClick={() => navigator.clipboard?.writeText(rec.raw)}>Copy</Button>
        </Space>
      )
    }
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <div style={{ color: 'white', fontWeight: 'bold' }}>Impactu OAI — Records</div>
      </Header>
      <Content style={{ padding: 24 }}>
        <Card style={{ marginBottom: 16 }}>
          <Title level={4}>Fetch OAI Records</Title>
          <p>Use an OAI query string (everything after <code>?<em>...</em></code>)</p>
          <Input value={query} onChange={(e) => setQuery(e.target.value)} style={{ marginBottom: 8 }} />
          <Space>
            <Button type="primary" onClick={fetchRecords} loading={loading}>Fetch</Button>
            <Button onClick={() => { setRecords([]); setSelectedXml(null) }}>Clear</Button>
          </Space>
        </Card>

        <Card style={{ marginBottom: 16 }} bodyStyle={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <Table dataSource={records} columns={columns} pagination={{ pageSize: 10 }} />
          </div>
          <div style={{ width: '45%' }}>
            <Title level={5}>XML Viewer</Title>
            <XMLViewer xml={selectedXml} />
          </div>
        </Card>
      </Content>
      <Footer style={{ textAlign: 'center' }}>Impactu — records inspector</Footer>
    </Layout>
  )
}
