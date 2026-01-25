import Head from 'next/head'
import { ConfigProvider, Layout } from 'antd'
import 'antd/dist/reset.css'
import '../styles/globals.css'
import NavBar from '../components/NavBar'
import SiteFooter from '../components/Footer'

const { Content } = Layout

export default function App({ Component, pageProps }) {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#328181',
          borderRadius: 8,
          fontFamily: 'Montserrat, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
        components: {
          Layout: {
            headerBg: '#3b72a1',
            bodyBg: '#f5f5f5',
          }
        }
      }}
    >
      <Head>
        <title>ImpactU | OAI-PMH Server</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <Layout style={{ minHeight: '100vh' }}>
        <NavBar />
        <Content>
          <div style={{ maxWidth: 1240, margin: '0 auto', padding: '40px 24px', width: '100%' }}>
            <Component {...pageProps} />
          </div>
        </Content>
        <SiteFooter />
      </Layout>
    </ConfigProvider>
  )
}
