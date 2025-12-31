import type { RouteObject } from 'react-router';

export const InboundBinding = () => {
  return (
    <div id="inbounds" className="tab-content active">
      <div className="section">
        <h2>Bind Template to Server</h2>
        <form id="inboundForm">
          <div className="form-group">
            <label>Server:</label>
            <select id="inboundServer" required>
              <option value="">Select Server...</option>
            </select>
          </div>
          <div className="form-group">
            <label>Template:</label>
            <select id="inboundTemplate" required>
              <option value="">Select Template...</option>
            </select>
          </div>
          <div className="form-group">
            <label>Port:</label>
            <input type="number" id="inboundPort" value="443" required />
          </div>
          <div className="form-group">
            <label>Certificate:</label>
            <select id="inboundCertificate">
              <option value="">No Certificate</option>
            </select>
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" id="inboundActive" checked /> Active
            </label>
          </div>
          <button type="submit" className="btn btn-primary">
            Bind Template
          </button>
        </form>
      </div>

      <div className="section">
        <h2>Server Inbounds</h2>
        <div id="inboundsList" className="loading">
          Loading...
        </div>
      </div>
    </div>
  );
};

export const InboundBindingRoute: RouteObject = {
  path: '/inbound-binding',
  Component: InboundBinding,
};
