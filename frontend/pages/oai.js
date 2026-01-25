import { Layout, Card, Typography } from 'antd'
const { Header, Content, Footer } = Layout
const { Title, Paragraph } = Typography

export default function OaiUI() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <div style={{ color: 'white', fontWeight: 'bold' }}>Impactu OAI</div>
      </Header>
      <Content style={{ padding: '24px' }}>
        <Card>
          <Title level={2}>OAI Browser View</Title>
          <Paragraph>
            This view is shown when a browser visits <code>/oai</code>. OAI clients that call
            <code>?verb=Identify</code> or other verbs will receive XML responses.
          </Paragraph>
        </Card>
      </Content>
      <Footer style={{ textAlign: 'center' }}>Impactu — frontend prototype</Footer>
    </Layout>
  )
}
