import type { RouteObject } from 'react-router';

export const InboundTemplates = () => {
  return (
    <div id="templates" className="tab-content active">
      <div className="section">
        <h2>Add Template</h2>
        <form id="templateForm">
          <div className="form-group">
            <label>Name:</label>
            <input type="text" id="templateName" required />
          </div>
          <div className="form-group">
            <label>Protocol:</label>
            <select id="templateProtocol" required>
              <option value="vless">VLESS</option>
              <option value="vmess">VMess</option>
              <option value="trojan">Trojan</option>
              <option value="shadowsocks">Shadowsocks</option>
            </select>
          </div>
          <div className="form-group">
            <label>Default Port:</label>
            <input type="number" id="templatePort" value="443" required />
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" id="templateTls" /> Requires TLS
            </label>
          </div>
          <div className="form-group">
            <label>Configuration Template:</label>
            <textarea
              id="templateConfig"
              rows={6}
              style={{
                width: '300px',
              }}
            ></textarea>
          </div>
          <button type="submit" className="btn btn-primary">
            Add Template
          </button>
        </form>
      </div>

      <div className="section">
        <h2>Templates List</h2>
        <div id="templatesList" className="loading">
          Loading...
        </div>
      </div>
    </div>
  );
};

export const InboundTemplatesRoute: RouteObject = {
  path: '/inbound-templates',
  Component: InboundTemplates,
};
