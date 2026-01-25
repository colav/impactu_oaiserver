import React from 'react'

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function formatXml(xml) {
  // simple indentation
  let formatted = ''
  const reg = /(>)(<)(\/*)/g
  xml = xml.replace(reg, '$1\n$2$3')
  let pad = 0
  xml.split('\n').forEach((node) => {
    let indent = 0
    if (node.match(/.+<\\/)) {
      indent = 0
    } else if (node.match(/<\\/)) {
      indent = 1
    }
    if (node.match(/<\\/)) {
      formatted += '  '.repeat(pad) + node + '\n'
    } else {
      formatted += '  '.repeat(pad) + node + '\n'
    }
    if (node.match(/<[^\/].*[^\/]>/) && !node.match(/<.*\/\>/)) {
      pad += 1
    }
    if (node.match(/<\/[^>]+>/)) {
      pad = Math.max(pad - 1, 0)
    }
  })
  return formatted
}

function highlightXml(xml) {
  // escape and then add spans for tag names and attributes
  let out = escapeHtml(xml)

  // highlight tag names: &lt; /?tag ... &gt;
  out = out.replace(/(&lt;\/?)([A-Za-z0-9_:\-\.]+)([^&]*?)(&gt;)/g, function(_, open, name, rest, close) {
    // highlight attributes inside rest
    const attrs = rest.replace(/([A-Za-z0-9_:\-\.]+)(=)(&quot;.*?&quot;|'.*?'|[^\s>]*)/g, '<span class="xml-attr-name">$1</span>$2<span class="xml-attr-value">$3</span>')
    return `${open}<span class="xml-tag-name">${name}</span>${attrs}${close}`
  })

  // comments
  out = out.replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span class="xml-comment">$1</span>')
  return out
}

export default function XMLViewer({ xml }) {
  if (!xml) return <div>No XML selected</div>
  const pretty = formatXml(xml)
  const highlighted = highlightXml(pretty)
  return (
    <div className="xml-viewer">
      <pre className="xml" dangerouslySetInnerHTML={{ __html: highlighted }} />
    </div>
  )
}
