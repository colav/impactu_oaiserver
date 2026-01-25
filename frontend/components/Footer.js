import { Layout, Row, Col, Divider, Space } from 'antd'

const { Footer: AntFooter } = Layout

export default function SiteFooter() {
  const impactuUrl = "https://impactu.colav.co"
  
  return (
    <AntFooter className="site-footer">
      <div style={{ maxWidth: '1240px', margin: '0 auto', padding: '0 24px' }}>
        <Row justify="center" align="middle">
          <Col span={24} style={{ textAlign: 'center' }}>
            <div className="footer-col-title">Fundadores:</div>
            <Row justify="center" align="middle" gutter={[48, 24]}>
              <Col><img src="/media/logo_udea.svg" alt="UdeA" style={{ height: 60 }} /></Col>
              <Col><img src="/media/logo_unaula.svg" alt="Unaula" style={{ height: 48 }} /></Col>
              <Col><img src="/media/logo_uec.svg" alt="Externado" style={{ height: 54 }} /></Col>
              <Col><img src="/media/logo_univalle.svg" alt="Univalle" style={{ height: 58 }} /></Col>
              <Col><img src="/media/logo_ascun.svg" alt="ASCUN" style={{ height: 48 }} /></Col>
            </Row>
          </Col>
        </Row>

        <Divider style={{ margin: '60px 0' }} />

        <Row gutter={[48, 32]}>
          <Col xs={24} md={8}>
            <div className="footer-col-title">Desarrollado por:</div>
            <img src="/media/logo_colav.svg" alt="Colav" style={{ height: 48, marginBottom: 20 }} />
            <div>
              <a href="https://github.com/colav" target="_blank" rel="noreferrer">@colav</a><br />
              <a href="mailto:grupocolav@udea.edu.co">Contacto</a>
            </div>
          </Col>

          <Col xs={24} md={8} style={{ textAlign: 'center' }}>
            <div className="footer-col-title">ImpactU:</div>
            <Space direction="vertical" size="small">
              <a href={`${impactuUrl}/about`} target="_blank" rel="noreferrer">Acerca de ImpactU</a>
              <a href={`${impactuUrl}/manual`} target="_blank" rel="noreferrer">Manual de usuario</a>
              <a href="https://github.com/colav/impactu_oaiserver" target="_blank" rel="noreferrer">Código Abierto</a>
            </Space>
          </Col>

          <Col xs={24} md={8} style={{ textAlign: 'right' }}>
            <div className="footer-col-title">Información:</div>
            <div>
              ImpactU OAI Server v1.0.0<br />
              Hecho en Colombia
            </div>
          </Col>
        </Row>
      </div>
    </AntFooter>
  )
}
