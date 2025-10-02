import type { RouteObject } from 'react-router';

export const Dashboard = () => {
  return (
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
  );
};

export const DashboardRoute: RouteObject = {
  index: true,
  path: '/',
  Component: Dashboard,
};
