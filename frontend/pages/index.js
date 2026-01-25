import { Layout, Menu, Typography, Card, Button } from 'antd'
const { Header, Content, Footer } = Layout
const { Title, Paragraph } = Typography

export default function Home() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <div style={{ color: 'white', fontWeight: 'bold' }}>Impactu OAI</div>
      </Header>
      <Content style={{ padding: '24px' }}>
        <Card>
          <Title level={2}>Impactu OAI-PMH</Title>
          <Paragraph>
            This is a minimal Next.js + Ant Design frontend. Use the buttons below to inspect the OAI endpoint.
          </Paragraph>
          <p>
            <Button type="primary" href="/oai?verb=Identify" target="_blank">
              View OAI Identify (XML)
            </Button>{' '}
            <Button href="/oai" target="_self">Open UI for /oai</Button>
          </p>
        </Card>
      </Content>
      <Footer style={{ textAlign: 'center' }}>Impactu — frontend prototype</Footer>
    </Layout>
  )
}
