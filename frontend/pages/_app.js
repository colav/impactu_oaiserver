import 'antd/dist/reset.css'
import '../styles/globals.css'
import '../styles/xmlviewer.css'
import NavBar from '../components/NavBar'

function AppLayout({ Component, pageProps }) {
  return (
    <>
      <NavBar />
      <Component {...pageProps} />
    </>
  )
}

export default function App(props) {
  return <AppLayout {...props} />
}
