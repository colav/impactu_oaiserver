import Link from 'next/link'
import { Layout, Row, Col, Input, Space, Button, Tooltip } from 'antd'
import { SearchOutlined, DatabaseOutlined } from '@ant-design/icons'
import { useRouter } from 'next/router'
import { useState } from 'react'

const { Header } = Layout

export default function NavBar() {
  const router = useRouter()
  const [searchVal, setSearchVal] = useState('')

  const onSearch = () => {
    if (!searchVal) return
    // Navigate to record detail if it looks like an ID, else just go to records list
    if (searchVal.includes(':') || searchVal.length > 20) {
      router.push(`/records/${encodeURIComponent(searchVal)}`)
    } else {
      router.push(`/records?verb=ListRecords&query=${encodeURIComponent(searchVal)}`)
    }
  }

  return (
    <Header style={{ 
      height: '80px', 
      display: 'flex', 
      alignItems: 'center',
      borderBottom: '1px solid #2d5a81',
      padding: '0 40px',
      position: 'sticky',
      top: 0,
      zIndex: 1000
    }}>
      <Row align="middle" justify="space-between" style={{ width: '100%', maxWidth: '1400px', margin: '0 auto' }}>
        {/* LOGO */}
        <Col xs={6} md={4}>
          <Link href="/">
            <img src="/media/logo_impactU_B.svg" alt="ImpactU" style={{ height: 48, cursor: 'pointer' }} />
          </Link>
        </Col>

        {/* SEARCH BAR (REDESIGNED TO BE PRODUCTIVE) */}
        <Col xs={12} md={12} style={{ display: 'flex', justifyContent: 'center' }}>
          <Space.Compact style={{ width: '100%', maxWidth: '600px' }}>
            <Input 
              placeholder="Buscar por ID de registro (OAI Identifier)..." 
              style={{ flex: 1, height: 44, borderRadius: '8px 0 0 8px' }} 
              value={searchVal}
              onChange={(e) => setSearchVal(e.target.value)}
              onPressEnter={onSearch}
              prefix={<DatabaseOutlined style={{ color: '#bfbfbf' }} />}
            />
            <Button 
               type="primary" 
               icon={<SearchOutlined />} 
               onClick={onSearch}
               style={{ height: 44, width: 60, borderRadius: '0 8px 8px 0', background: '#328181', borderColor: '#328181' }}
            />
          </Space.Compact>
        </Col>

        {/* NAVIGATION */}
        <Col xs={6} md={4} style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Space size="large">
            <Link href="/records">
              <Button type="text" style={{ color: '#ffffff', fontWeight: 600 }}>
                Explorar
              </Button>
            </Link>
          </Space>
        </Col>
      </Row>
    </Header>
  )
}
