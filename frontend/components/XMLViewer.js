import React from 'react'

export default function XMLViewer({ xml }) {
  if (!xml) return null

  // Basic XML indentation
  const formatXML = (xmlString) => {
    let indent = '';
    const tab = '  ';
    let formatted = '';
    const reg = /(>)(<)(\/*)/g;
    xmlString = xmlString.replace(reg, '\r\n');
    let pad = 0;
    xmlString.split('\r\n').forEach((node) => {
      let indent = 0;
      if (node.match(/.+<\/\w[^>]*>$/)) {
        indent = 0;
      } else if (node.match(/^<\/\w/)) {
        if (pad !== 0) {
          pad -= 1;
        }
      } else if (node.match(/^<\w([^>]*[^\/])?>.*$/)) {
        indent = 1;
      } else {
        indent = 0;
      }

      formatted += tab.repeat(pad) + node + '\r\n';
      pad += indent;
    });
    return formatted.trim();
  }

  return (
    <div style={{ position: 'relative' }}>
      <pre style={{ 
        background: '#1e1e1e', 
        color: '#d4d4d4', 
        padding: '20px', 
        borderRadius: '8px', 
        overflow: 'auto',
        fontSize: '13px',
        lineHeight: '1.5',
        maxHeight: '600px',
        border: '1px solid #333',
        fontFamily: "'Fira Code', 'Consolas', monospace"
      }}>
        <code>{formatXML(xml)}</code>
      </pre>
    </div>
  )
}
