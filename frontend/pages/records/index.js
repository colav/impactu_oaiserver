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
  const [nextToken, setNextToken] = useState(null)
  const [tokenStack, setTokenStack] = useState([])
  const [initialQuery, setInitialQuery] = useState(query)

  function extractPreviewFromRecord(recordElem) {
    try {
      const md = recordElem.getElementsByTagName('metadata')[0]
      if (!md) return {}
      // try to find Title element (namespace-agnostic)
      const titleEl = md.getElementsByTagName('Title')[0] || md.getElementsByTagName('title')[0]
      const title = titleEl?.textContent?.trim() || ''
      // authors: look for Authors/Author/Person or Person elements with Name
      let authors = []
      const authorsEls = md.getElementsByTagName('Authors')
      if (authorsEls && authorsEls.length) {
        const names = authorsEls[0].getElementsByTagName('Person')
        for (let i = 0; i < names.length; i++) {
          const n = names[i].textContent.trim()
          if (n) authors.push(n)
        }
      }
      if (!authors.length) {
        const personEls = md.getElementsByTagName('Person')
        for (let i = 0; i < personEls.length; i++) {
          const n = personEls[i].textContent.trim()
          if (n) authors.push(n)
        }
      }
      // DOI
      const doiEl = md.getElementsByTagName('DOI')[0]
      const doi = doiEl?.textContent?.trim() || ''
      return { title, authors, doi }
    } catch (e) {
      return {}
    }
  }

  async function fetchRecords(url) {
    setLoading(true)
    try {
      const res = await fetch(url)
      const text = await res.text()
      const doc = new DOMParser().parseFromString(text, 'application/xml')

      // handle resumptionToken
      const rt = doc.getElementsByTagName('resumptionToken')[0]
      const next = rt?.textContent?.trim() || null
      setNextToken(next)

      const recElems = Array.from(doc.getElementsByTagName('record'))
      const recs = recElems.map((r) => {
        const header = r.getElementsByTagName('header')[0]
        const ident = header?.getElementsByTagName('identifier')[0]?.textContent || ''
        const datestamp = header?.getElementsByTagName('datestamp')[0]?.textContent || ''
        let entity = ''
        const md = r.getElementsByTagName('metadata')[0]
        if (md && md.firstElementChild) entity = md.firstElementChild.localName
        const preview = extractPreviewFromRecord(r)
        return { key: ident + '|' + datestamp, ident, datestamp, entity, raw: new XMLSerializer().serializeToString(r), preview }
      })
      setRecords(recs)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  function startFetchInitial() {
    // clear pagination stack
    setTokenStack([])
    setInitialQuery(query)
    const url = '/oai?' + query
    fetchRecords(url)
  }

  function fetchNext() {
    if (!nextToken) return
    // push current token (could be null for first page)
    setTokenStack((s) => [...s, nextToken])
    const url = '/oai?verb=ListRecords&resumptionToken=' + encodeURIComponent(nextToken)
    fetchRecords(url)
  }

  function fetchPrev() {
    setTokenStack((s) => {
      if (!s.length) {
        // go back to initial query
        fetchRecords('/oai?' + initialQuery)
        return []
      }
      const copy = s.slice(0, -1)
      const prevToken = copy[copy.length - 1] || null
      const url = prevToken ? '/oai?verb=ListRecords&resumptionToken=' + encodeURIComponent(prevToken) : '/oai?' + initialQuery
      fetchRecords(url)
      return copy
    })
  }

  const columns = [
    { title: 'Identifier', dataIndex: 'ident', key: 'ident', render: (t) => <a href={`/records/${encodeURIComponent(t)}`}>{t}</a> },
    { title: 'Date', dataIndex: 'datestamp', key: 'datestamp' },
    { title: 'Entity', dataIndex: 'entity', key: 'entity', render: (t) => <Tag color="blue">{t || 'Unknown'}</Tag> },
    { title: 'Title', dataIndex: ['preview', 'title'], key: 'title', render: (t) => t ? <span style={{fontWeight:500}}>{t}</span> : null },
    { title: 'Authors', dataIndex: ['preview', 'authors'], key: 'authors', render: (a) => (a && a.length) ? a.slice(0,3).map((n,i)=>(<div key={i} style={{fontSize:12}}>{n}</div>)) : null },
    { title: 'DOI', dataIndex: ['preview', 'doi'], key: 'doi', render: (d) => d ? <a href={d.startsWith('http')?d:`https://doi.org/${d}`} target="_blank" rel="noreferrer">{d}</a> : null },
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
            <Button type="primary" onClick={startFetchInitial} loading={loading}>Fetch</Button>
            <Button onClick={() => { setRecords([]); setSelectedXml(null); setNextToken(null); setTokenStack([]) }}>Clear</Button>
            <Button onClick={fetchPrev} disabled={tokenStack.length===0}>Prev</Button>
            <Button onClick={fetchNext} disabled={!nextToken}>Next</Button>
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
