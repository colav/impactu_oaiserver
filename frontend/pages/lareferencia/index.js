import { useState, useEffect } from 'react'
import {
  Card, Typography, Row, Col, Button, Spin, Statistic, Space, Divider,
  Alert, Table, Tag, Collapse, Steps
} from 'antd'
import {
  InfoCircleOutlined, DatabaseOutlined, ApiOutlined, BankOutlined,
  CloudDownloadOutlined, CodeOutlined, FileSearchOutlined, ArrowRightOutlined,
  CheckCircleOutlined
} from '@ant-design/icons'
import Link from 'next/link'

const { Title, Paragraph, Text } = Typography

// Path of the OAI-PMH harvesting endpoint (proxied to the backend).
const HARVEST_PATH = '/lareferencia/oai'

// Code block helper — keeps a consistent monospace style across the page.
function Code({ children, block }) {
  if (block) {
    return (
      <pre style={{
        background: '#073b3b', color: '#d6f5f5', padding: '14px 18px',
        borderRadius: 8, overflowX: 'auto', fontSize: 13, lineHeight: 1.6,
        margin: '8px 0'
      }}>{children}</pre>
    )
  }
  return <Text code style={{ fontSize: 13 }}>{children}</Text>
}

const VERBS = [
  {
    verb: 'Identify',
    desc: 'Información general del repositorio (nombre, versión del protocolo, granularidad).',
    example: '?verb=Identify',
  },
  {
    verb: 'ListMetadataFormats',
    desc: 'Formatos de metadatos disponibles. Este repositorio sirve únicamente el perfil dim de DSpace.',
    example: '?verb=ListMetadataFormats',
  },
  {
    verb: 'ListSets',
    desc: 'Catálogo de conjuntos (sets). Cada institución es un set, identificado por su acrónimo.',
    example: '?verb=ListSets',
  },
  {
    verb: 'ListIdentifiers',
    desc: 'Lista solo las cabeceras (identificador, fecha, sets) de los registros.',
    example: '?verb=ListIdentifiers&metadataPrefix=dim',
  },
  {
    verb: 'ListRecords',
    desc: 'Cosecha completa: cabecera + metadatos XML de cada registro. Es el verbo principal de cosecha.',
    example: '?verb=ListRecords&metadataPrefix=dim',
  },
  {
    verb: 'GetRecord',
    desc: 'Devuelve un único registro a partir de su identificador OAI.',
    example: '?verb=GetRecord&metadataPrefix=dim&identifier=oai:repositorio.unaula.edu.co:123456789/1856',
  },
]

const PARAMS = [
  { p: 'verb', req: 'Sí', d: 'Operación OAI-PMH a ejecutar (ver tabla de verbos).' },
  { p: 'metadataPrefix', req: 'Sí *', d: 'Formato de metadatos. Único valor admitido: dim.' },
  { p: 'set', req: 'No', d: 'Acrónimo de la institución a cosechar (p. ej. unaula). Si se omite, se cosechan todas.' },
  { p: 'from', req: 'No', d: 'Fecha inicial (YYYY-MM-DD). Filtra por la fecha del registro (datestamp).' },
  { p: 'until', req: 'No', d: 'Fecha final (YYYY-MM-DD).' },
  { p: 'resumptionToken', req: 'No', d: 'Token de continuación entregado por el servidor para paginar la cosecha. Conserva los filtros y el tamaño de página entre peticiones.' },
]

export default function LaReferenciaHome() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [origin, setOrigin] = useState('')

  useEffect(() => {
    setOrigin(window.location.origin)
    fetch('/lareferencia/stats')
      .then(res => {
        if (!res.ok) throw new Error('stats no disponible')
        return res.json()
      })
      .then(data => setStats(data))
      .catch(err => console.error('Error fetching LaReferencia stats:', err))
      .finally(() => setLoading(false))
  }, [])

  const harvestUrl = (origin || 'https://oai.impactu.colav.co') + HARVEST_PATH
  const institutionCount = stats ? Object.keys(stats).filter(k => k !== 'total').length : 0

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" tip="Cargando información del repositorio..." />
      </div>
    )
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* HERO */}
      <div style={{ padding: '32px 0', textAlign: 'center' }}>
        <Tag color="cyan" style={{ fontSize: 13, padding: '4px 12px', marginBottom: 16 }}>
          OAI-PMH · LaReferencia
        </Tag>
        <Title level={1} style={{ marginBottom: 16 }}>
          Repositorios DSpace de Colombia
        </Title>
        <Paragraph style={{ fontSize: 19, color: '#666', maxWidth: 820, margin: '0 auto' }}>
          Punto único de cosecha OAI-PMH que agrega los metadatos de los repositorios
          institucionales DSpace del país, listos para ser cosechados por LaReferencia
          y otros agregadores de acceso abierto.
        </Paragraph>
        <Space style={{ marginTop: 28 }} wrap>
          <Link href="/lareferencia/instituciones">
            <Button type="primary" size="large" icon={<BankOutlined />}
              style={{ height: 48, padding: '0 28px', background: '#328181', borderColor: '#328181' }}>
              Ver instituciones
            </Button>
          </Link>
          <Button size="large" icon={<ApiOutlined />} href={`${HARVEST_PATH}?verb=Identify`} target="_blank"
            style={{ height: 48, padding: '0 28px' }}>
            Probar endpoint (Identify)
          </Button>
        </Space>
      </div>

      {/* METRICS */}
      <Row gutter={[24, 24]}>
        <Col xs={24} md={8}>
          <Card bordered={false} className="record-card" style={{ background: '#3b72a1', color: 'white' }}>
            <Statistic
              title={<span style={{ color: 'rgba(255,255,255,0.85)' }}>Registros disponibles</span>}
              value={stats?.total}
              valueStyle={{ color: 'white', fontWeight: 800, fontSize: 32 }}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} className="record-card">
            <Statistic
              title="Instituciones (sets)"
              value={institutionCount}
              prefix={<BankOutlined />}
              valueStyle={{ color: '#073b3b' }}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} className="record-card">
            <Statistic
              title="Formato de metadatos"
              value="dim"
              prefix={<CodeOutlined />}
              valueStyle={{ color: '#073b3b' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider />

      {/* QUÉ ES */}
      <Row gutter={[32, 32]} id="acerca">
        <Col xs={24} lg={14}>
          <Title level={3}>¿Qué es este servicio?</Title>
          <Paragraph style={{ fontSize: 16 }}>
            Los repositorios institucionales DSpace de Colombia son cosechados y almacenados
            periódicamente. Este servidor los reexpone como un <Text strong>único proveedor de
            datos OAI-PMH 2.0</Text>, de modo que LaReferencia puede recolectar la producción
            académica de todo el país desde un solo punto de acceso.
          </Paragraph>
          <Paragraph style={{ fontSize: 16 }}>
            Cada institución se publica como un <Text strong>set</Text> de OAI-PMH. Los registros
            se entregan en el perfil <Code>dim</Code> (DSpace Intermediate Metadata), tal como
            fueron cosechados del repositorio de origen, sin transformaciones.
          </Paragraph>
          <Alert
            style={{ marginTop: 8 }}
            message="Endpoint de cosecha"
            description={<Code>{harvestUrl}</Code>}
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
          />
        </Col>
        <Col xs={24} lg={10}>
          <Card title={<span><CheckCircleOutlined /> Características</span>}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div><Tag color="green">OAI-PMH 2.0</Tag> Cumple el protocolo estándar.</div>
              <div><Tag color="cyan">dim</Tag> Perfil DSpace Intermediate Metadata.</div>
              <div><Tag color="blue">{institutionCount} sets</Tag> Un set por institución.</div>
              <div><Tag color="gold">resumptionToken</Tag> Paginación para cosecha masiva.</div>
              <div><Tag color="purple">from / until</Tag> Cosecha incremental por fecha.</div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Divider />

      {/* GUÍA DE COSECHA */}
      <div id="cosecha">
        <Title level={3}><CloudDownloadOutlined /> Guía de cosecha</Title>
        <Paragraph style={{ fontSize: 16 }}>
          Configure su cosechador (LaReferencia, u otro cliente OAI-PMH) apuntando al endpoint
          y siguiendo estos pasos.
        </Paragraph>
        <Steps
          direction="vertical"
          current={-1}
          style={{ marginTop: 16, maxWidth: 900 }}
          items={[
            {
              title: 'Registrar el endpoint',
              description: <span>Use la URL base <Code>{harvestUrl}</Code> con el formato de metadatos <Code>dim</Code>.</span>,
            },
            {
              title: 'Elegir el alcance',
              description: 'Cosecha total (todas las instituciones) o por set, indicando el acrónimo de una institución en el parámetro set.',
            },
            {
              title: 'Paginar con resumptionToken',
              description: 'Cuando la respuesta incluya un <resumptionToken> con valor, repita la petición usando ese token. El atributo completeListSize indica el total de registros y cursor cuántos se han entregado. La cosecha termina cuando el token llega vacío.',
            },
            {
              title: 'Cosecha incremental',
              description: 'En cosechas posteriores use from y until (YYYY-MM-DD) para recolectar solo lo modificado en un rango de fechas.',
            },
          ]}
        />
      </div>

      {/* VERBOS */}
      <Card id="verbos" title={<span><ApiOutlined /> Verbos OAI-PMH</span>}>
        <Table
          dataSource={VERBS.map((v, i) => ({ key: i, ...v }))}
          pagination={false}
          size="middle"
          columns={[
            {
              title: 'Verbo',
              dataIndex: 'verb',
              width: 200,
              render: (v) => <Text strong style={{ color: '#328181' }}>{v}</Text>,
            },
            { title: 'Descripción', dataIndex: 'desc' },
            {
              title: 'Ejemplo',
              dataIndex: 'example',
              width: 130,
              render: (ex) => (
                <Button size="small" type="link" href={`${HARVEST_PATH}${ex}`} target="_blank">
                  Probar
                </Button>
              ),
            },
          ]}
        />
      </Card>

      {/* PARÁMETROS */}
      <Card id="parametros" title={<span><FileSearchOutlined /> Parámetros admitidos</span>}>
        <Table
          dataSource={PARAMS.map((p, i) => ({ key: i, ...p }))}
          pagination={false}
          size="middle"
          columns={[
            {
              title: 'Parámetro',
              dataIndex: 'p',
              width: 200,
              render: (p) => <Code>{p}</Code>,
            },
            {
              title: 'Requerido',
              dataIndex: 'req',
              width: 120,
              render: (r) => <Tag color={r.startsWith('Sí') ? 'red' : 'default'}>{r}</Tag>,
            },
            { title: 'Descripción', dataIndex: 'd' },
          ]}
        />
        <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 13 }}>
          * <Code>metadataPrefix</Code> es obligatorio en ListRecords, ListIdentifiers y GetRecord;
          no se usa cuando se pagina con <Code>resumptionToken</Code>.
        </Paragraph>
      </Card>

      {/* EJEMPLOS */}
      <Card id="ejemplos" title={<span><CodeOutlined /> Ejemplos de uso</span>}>
        <Collapse
          defaultActiveKey={['1']}
          items={[
            {
              key: '1',
              label: 'Cosecha completa de un repositorio',
              children: (
                <>
                  <Paragraph>Cosechar todos los registros de la Universidad Autónoma Latinoamericana (set <Code>unaula</Code>):</Paragraph>
                  <Code block>{`curl "${harvestUrl}?verb=ListRecords&metadataPrefix=dim&set=unaula"`}</Code>
                </>
              ),
            },
            {
              key: '2',
              label: 'Continuar la cosecha (paginación)',
              children: (
                <>
                  <Paragraph>La respuesta termina con un <Code>{'<resumptionToken>TOKEN</resumptionToken>'}</Code>. Para la siguiente página:</Paragraph>
                  <Code block>{`curl "${harvestUrl}?verb=ListRecords&resumptionToken=TOKEN"`}</Code>
                </>
              ),
            },
            {
              key: '3',
              label: 'Cosecha incremental por fecha',
              children: (
                <>
                  <Paragraph>Recolectar solo lo modificado en un rango de fechas:</Paragraph>
                  <Code block>{`curl "${harvestUrl}?verb=ListRecords&metadataPrefix=dim&from=2024-01-01&until=2024-12-31"`}</Code>
                </>
              ),
            },
            {
              key: '4',
              label: 'Obtener un registro puntual',
              children: (
                <Code block>{`curl "${harvestUrl}?verb=GetRecord&metadataPrefix=dim&identifier=oai:repositorio.unaula.edu.co:123456789/1856"`}</Code>
              ),
            },
          ]}
        />
      </Card>

      {/* CTA INSTITUCIONES */}
      <Card style={{ background: '#f0f7f7', border: '1px solid #cfe5e5' }}>
        <Row align="middle" justify="space-between" gutter={[16, 16]}>
          <Col xs={24} md={16}>
            <Title level={4} style={{ margin: 0 }}>Catálogo de instituciones</Title>
            <Paragraph style={{ margin: '8px 0 0' }}>
              Consulte el listado completo de repositorios, su número de registros y el
              enlace de cosecha de cada uno.
            </Paragraph>
          </Col>
          <Col xs={24} md={8} style={{ textAlign: 'right' }}>
            <Link href="/lareferencia/instituciones">
              <Button type="primary" size="large" icon={<ArrowRightOutlined />}
                style={{ background: '#328181', borderColor: '#328181' }}>
                Ver instituciones
              </Button>
            </Link>
          </Col>
        </Row>
      </Card>
    </Space>
  )
}
