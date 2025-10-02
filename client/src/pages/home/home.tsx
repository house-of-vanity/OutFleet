import { Outlet } from 'react-router';
import './home.css';

export const Home = () => {
  return (
    <div>
      <div className="container">
        <h1>Xray Admin Panel - Test Interface</h1>

        {/* <!-- Toast notifications container --> */}
        <div className="toast-container" id="toastContainer"></div>

        <div className="tabs">
          <div
            className="tab active"
            //   onClick="showTab('dashboard')"
          >
            Dashboard
          </div>
          <div
            className="tab"
            // onClick="showTab('servers')"
          >
            Servers
          </div>
          <div
            className="tab"
            //onClick="showTab('templates')"
          >
            Inbound Templates
          </div>
          <div
            className="tab"
            // onClick="showTab('certificates')"
          >
            Certificates
          </div>
          <div
            className="tab"
            // onClick="showTab('inbounds')"
          >
            Inbound Binding
          </div>
          <div
            className="tab"
            // onClick="showTab('users')"
          >
            Users
          </div>
        </div>

        {/* <!-- Dashboard --> */}
        <div id="dashboard" className="tab-content active">
          <div className="section">
            <h2>Statistics</h2>
            <p>
              Servers: <span id="serverCount">Loading...</span>
            </p>
            <p>
              Templates: <span id="templateCount">Loading...</span>
            </p>
            <p>
              Certificates: <span id="certCount">Loading...</span>
            </p>
            <p>
              Users: <span id="userCount">Loading...</span>
            </p>
          </div>
        </div>

        {/* <!-- Servers --> */}
        <div id="servers" className="tab-content">
          <div className="section">
            <h2>Add Server</h2>
            <form id="serverForm">
              <div className="form-group">
                <label>Name:</label>
                <input type="text" id="serverName" required />
              </div>
              <div className="form-group">
                <label>Hostname:</label>
                <input type="text" id="serverHostname" required />
              </div>
              <div className="form-group">
                <label>gRPC Port:</label>
                <input type="number" id="serverPort" value="2053" />
              </div>
              <button type="submit" className="btn btn-primary">
                Add Server
              </button>
            </form>
          </div>

          <div className="section">
            <h2>Servers List</h2>
            <div id="serversList" className="loading">
              Loading...
            </div>
          </div>
        </div>

        {/* <!-- Templates --> */}
        <div id="templates" className="tab-content">
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

        {/* <!-- Certificates --> */}
        <div id="certificates" className="tab-content">
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
                  <input type="checkbox" id="certAutoRenew" checked /> Auto
                  Renew
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

        {/* <!-- Server Inbounds --> */}
        <div id="inbounds" className="tab-content">
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

        {/* <!-- Users --> */}
        <div id="users" className="tab-content">
          <div className="section">
            <h2>Add User</h2>
            <form id="userForm">
              <div className="form-group">
                <label>Name:</label>
                <input type="text" id="userName" required />
              </div>
              <div className="form-group">
                <label>Comment:</label>
                <input type="text" id="userComment" />
              </div>
              <div className="form-group">
                <label>Telegram ID:</label>
                <input type="number" id="userTelegram" />
              </div>
              <button type="submit" className="btn btn-primary">
                Add User
              </button>
            </form>
          </div>

          <div className="section">
            <h2>Users List</h2>
            <div id="usersList" className="loading">
              Loading...
            </div>
          </div>
        </div>
      </div>

      {/* <!-- Modal dialogs --> */}
      <div id="editModal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <div className="modal-title" id="editModalTitle">
              Edit Item
            </div>
            <button
              className="modal-close"
              // onClick="closeModal('editModal')"
            >
              &times;
            </button>
          </div>
          <div className="modal-body" id="editModalBody">
            {/* <!-- Content will be dynamically loaded --> */}
          </div>
          <div className="modal-footer">
            <button
              className="btn btn-secondary"
              // onClick="closeModal('editModal')"
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              id="saveEditBtn"
              // onClick="saveEdit()"
            >
              Save
            </button>
          </div>
        </div>
      </div>

      <div id="viewModal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <div className="modal-title" id="viewModalTitle">
              View Details
            </div>
            <button
              className="modal-close"
              //onClick="closeModal('viewModal')"
            >
              &times;
            </button>
          </div>
          <div className="modal-body" id="viewModalBody">
            {/* <!-- Content will be dynamically loaded --> */}
          </div>
          <div className="modal-footer">
            <button
              className="btn btn-secondary"
              //   onClick="closeModal('viewModal')"
            >
              Close
            </button>
          </div>
        </div>
      </div>
      <Outlet />
    </div>
  );
};
