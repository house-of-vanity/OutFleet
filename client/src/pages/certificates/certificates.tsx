import type { RouteObject } from 'react-router';

export const Certificates = () => {
  return (
    <div id="certificates" className="tab-content active">
      <div className="section">
        <h2>Add Certificate</h2>
        <form id="certificateForm">
          <div className="form-group">
            <label>Name:</label>
            <input type="text" id="certName" required />
          </div>
          <div className="form-group">
            <label>Domain:</label>
            <input
              type="text"
              id="certDomain"
              placeholder="example.com"
              required
            />
          </div>
          <div className="form-group">
            <label>Certificate Type:</label>
            <select id="certType" required>
              <option value="self_signed">Self-Signed</option>
            </select>
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" id="certAutoRenew" checked /> Auto Renew
            </label>
          </div>
          <button type="submit" className="btn btn-primary">
            Generate Certificate
          </button>
        </form>
      </div>

      <div className="section">
        <h2>Certificates List</h2>
        <div id="certificatesList" className="loading">
          Loading...
        </div>
      </div>
    </div>
  );
};

export const CertificatesRoute: RouteObject = {
  path: '/certificates',
  Component: Certificates,
};
