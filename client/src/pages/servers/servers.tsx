import type { RouteObject } from 'react-router';

export const Servers = () => {
  return (
    <div id="servers" className="tab-content active">
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
  );
};

export const ServersRoute: RouteObject = {
  path: '/servers',
  Component: Servers,
};
