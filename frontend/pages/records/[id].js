import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { Card, Button, Typography, Tag, Space } from 'antd'
import XMLViewer from '../../components/XMLViewer'

const { Title, Paragraph } = Typography

export default function RecordDetail() {
  const router = useRouter()
  const { id } = router.query
  const [xml, setXml] = useState(null)
  const [preview, setPreview] = useState({})

  useEffect(() => {
    if (!id) return
    const identifier = decodeURIComponent(id)
    const url = `/oai?verb=GetRecord&identifier=${encodeURIComponent(identifier)}&metadataPrefix=oai_cerif_openaire_1.2`
    fetch(url)
      .then((r) => r.text())
      .then((t) => {
        setXml(t)
        // try parse preview
        try {
          const doc = new DOMParser().parseFromString(t, 'application/xml')
          const record = doc.getElementsByTagName('record')[0]
          if (record) {
            const md = record.getElementsByTagName('metadata')[0]
            const titleEl = md?.getElementsByTagName('Title')[0] || md?.getElementsByTagName('title')[0]
            const title = titleEl?.textContent?.trim() || ''
            const authors = Array.from(md?.getElementsByTagName('Person')||[]).map(p=>p.textContent.trim()).slice(0,5)
            const doi = md?.getElementsByTagName('DOI')[0]?.textContent || ''
            setPreview({ title, authors, doi })
          }
        } catch (e) {}
      })
  }, [id])

  function downloadXml() {
    const blob = new Blob([xml || ''], { type: 'application/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = (id || 'record') + '.xml'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Title level={3}>Record: {id}</Title>
          {preview.title && <Paragraph><strong>Title:</strong> {preview.title}</Paragraph>}
          {preview.authors && preview.authors.length>0 && <Paragraph><strong>Authors:</strong> {preview.authors.join(', ')}</Paragraph>}
          {preview.doi && <Paragraph><strong>DOI:</strong> <a href={`https://doi.org/${preview.doi}`} target="_blank" rel="noreferrer">{preview.doi}</a></Paragraph>}
          <Space>
            <Button onClick={downloadXml} disabled={!xml}>Download XML</Button>
            <Button onClick={() => router.back()}>Back</Button>
          </Space>
        </Space>
      </Card>
      <div style={{ marginTop: 16 }}>
        <Title level={4}>Raw XML</Title>
        <XMLViewer xml={xml} />
      </div>
    </div>
  )
}
