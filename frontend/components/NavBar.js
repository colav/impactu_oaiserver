import Link from 'next/link'
import { Menu } from 'antd'

export default function NavBar() {
  return (
    <Menu theme="dark" mode="horizontal" selectable={false}>
      <Menu.Item key="home"><Link href="/">Home</Link></Menu.Item>
      <Menu.Item key="records"><Link href="/records">Records</Link></Menu.Item>
      <Menu.Item key="publications"><Link href="/records?entity=Publication">Publications</Link></Menu.Item>
      <Menu.Item key="persons"><Link href="/records?entity=Person">Persons</Link></Menu.Item>
      <Menu.Item key="orgs"><Link href="/records?entity=OrgUnit">Org Units</Link></Menu.Item>
    </Menu>
  )
}
