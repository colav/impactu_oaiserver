import { useState, useEffect } from 'react'
import {
  Card, Typography, Table, Input, Tag, Button, Space, Spin, Alert,
  Statistic, Row, Col, Tooltip
} from 'antd'
import {
  SearchOutlined, BankOutlined, DatabaseOutlined, DownloadOutlined,
  ApiOutlined, ArrowLeftOutlined
} from '@ant-design/icons'
import Link from 'next/link'

const { Title, Paragraph, Text } = Typography

const HARVEST_PATH = '/lareferencia/oai'

export default function Instituciones() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    async function load() {
      try {
        // Counts per institution acronym.
        const statsRes = await fetch('/lareferencia/stats')
        if (!statsRes.ok) throw new Error(`stats HTTP ${statsRes.status}`)
        const stats = await statsRes.json()

        // Human-readable names come from ListSets (setSpec = acronym, setName = repo name).
        const names = {}
        try {
          const setsRes = await fetch(`${HARVEST_PATH}?verb=ListSets`)
          const xml = await setsRes.text()
          const doc = new DOMParser().parseFromString(xml, 'text/xml')
          const setNodes = Array.from(doc.getElementsByTagName('set'))
          setNodes.forEach(node => {
            const spec = node.getElementsByTagName('setSpec')[0]?.textContent
            const name = node.getElementsByTagName('setName')[0]?.textContent
            if (spec) names[spec] = name || spec
          })
        } catch (e) {
          console.warn('No se pudo cargar ListSets:', e)
        }

        const data = Object.entries(stats)
          .filter(([key]) => key !== 'total')
          .map(([acronym, count]) => ({
            key: acronym,
            acronym,
            name: names[acronym] || acronym,
            count,
          }))
          .sort((a, b) => b.count - a.count)

        setRows(data)
        setTotal(stats.total || 0)
      } catch (e) {
        console.error(e)
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = rows.filter(r =>
    r.name.toLowerCase().includes(search.toLowerCase()) ||
    r.acronym.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    {
      title: 'Institución',
      dataIndex: 'name',
      render: (name, row) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Tag color="cyan" style={{ marginTop: 2 }}>{row.acronym}</Tag>
        </Space>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Registros',
      dataIndex: 'count',
      width: 160,
      align: 'right',
      defaultSortOrder: 'descend',
      sorter: (a, b) => a.count - b.count,
      render: (count) => <Text strong style={{ color: '#073b3b' }}>{count.toLocaleString('es-CO')}</Text>,
    },
    {
      title: 'set (OAI)',
      dataIndex: 'acronym',
      width: 150,
      render: (acronym) => <Text code>{acronym}</Text>,
    },
    {
      title: 'Cosecha',
      key: 'actions',
      width: 200,
      render: (_, row) => (
        <Space>
          <Tooltip title="Cosechar este repositorio (ListRecords, formato dim)">
            <Button
              size="small"
              type="primary"
              icon={<DownloadOutlined />}
              href={`${HARVEST_PATH}?verb=ListRecords&metadataPrefix=dim&set=${row.acronym}`}
              target="_blank"
              style={{ background: '#328181', borderColor: '#328181' }}
            >
              ListRecords
            </Button>
          </Tooltip>
          <Tooltip title="Ver solo identificadores">
            <Button
              size="small"
              icon={<ApiOutlined />}
              href={`${HARVEST_PATH}?verb=ListIdentifiers&metadataPrefix=dim&set=${row.acronym}`}
              target="_blank"
            />
          </Tooltip>
        </Space>
      ),
    },
  ]

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" tip="Cargando catálogo de instituciones..." />
      </div>
    )
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Link href="/lareferencia">
          <Button type="link" icon={<ArrowLeftOutlined />} style={{ paddingLeft: 0 }}>
            Volver a LaReferencia
          </Button>
        </Link>
        <Title level={2} style={{ margin: '8px 0 4px' }}>
          <BankOutlined /> Instituciones
        </Title>
        <Paragraph style={{ color: '#666', fontSize: 16 }}>
          Repositorios DSpace cosechados. Cada institución es un <Text strong>set</Text> de
          OAI-PMH; use su acrónimo en el parámetro <Text code>set</Text> para cosechar solo
          ese repositorio.
        </Paragraph>
      </div>

      <Row gutter={[24, 24]}>
        <Col xs={24} md={8}>
          <Card bordered={false} className="record-card">
            <Statistic title="Instituciones" value={rows.length} prefix={<BankOutlined />}
              valueStyle={{ color: '#073b3b' }} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} className="record-card">
            <Statistic title="Registros totales" value={total} prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#073b3b' }} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} className="record-card" style={{ background: '#3b72a1' }}>
            <Statistic
              title={<span style={{ color: 'rgba(255,255,255,0.85)' }}>Cosecha total</span>}
              value="dim"
              valueStyle={{ color: 'white' }}
              prefix={<DownloadOutlined />}
            />
            <Button
              size="small" block style={{ marginTop: 12 }}
              href={`${HARVEST_PATH}?verb=ListRecords&metadataPrefix=dim`}
              target="_blank"
            >
              Cosechar todo
            </Button>
          </Card>
        </Col>
      </Row>

      {error && (
        <Alert type="warning" showIcon message="No se pudieron cargar los datos" description={error} />
      )}

      <Card>
        <Input
          placeholder="Buscar institución por nombre o acrónimo..."
          prefix={<SearchOutlined />}
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
          style={{ maxWidth: 420, marginBottom: 16 }}
        />
        <Table
          columns={columns}
          dataSource={filtered}
          pagination={{ pageSize: 25, showSizeChanger: true, showTotal: (t) => `${t} instituciones` }}
          size="middle"
        />
      </Card>
    </Space>
  )
}
