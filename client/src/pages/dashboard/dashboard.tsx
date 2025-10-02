import type { RouteObject } from 'react-router';
import {
  getServers,
  getTemplates,
  getCertificates,
  getUsers,
  type Server,
  type Template,
  type Certificate,
  type User,
} from '../../api';
import { useEffect, useState } from 'react';

export const loadDashboard = async () => {
  try {
    const [servers, templates, certificates, users] = await Promise.all([
      getServers.then((data) => data),
      getTemplates.then((data) => data),
      getCertificates.then((data) => data),
      getUsers.then((data) => data),
    ]);

    return [servers, templates, certificates, users];
  } catch (error) {
    console.log(error);
    alert('loading error');
  }
};

export const Dashboard = () => {
  const [servers, setServers] = useState<Server[] | undefined>(undefined);
  const [templates, setTemplates] = useState<Template[] | undefined>(undefined);
  const [certificates, setCertificates] = useState<Certificate[] | undefined>(
    undefined,
  );
  const [users, setUsers] = useState<User[] | undefined>(undefined);

  useEffect(() => {
    loadDashboard()
      .then((res) => {
        if (res) {
          const [servers, templates, certificates, users] = res;
          setServers(servers);
          setTemplates(templates);
          setCertificates(certificates);
          setUsers(users);
        }
      })
      .catch((e) => {
        console.log(e);
      });
  }, []);

  return (
    <div id="dashboard" className="tab-content active">
      <div className="section">
        <h2>Statistics</h2>
        <p>
          Servers:{' '}
          <span id="serverCount">
            {servers ? servers.length || 0 : 'Loading...'}
          </span>
        </p>
        <p>
          Templates:{' '}
          <span id="templateCount">
            {templates ? templates.length || 0 : 'Loading...'}
          </span>
        </p>
        <p>
          Certificates:{' '}
          <span id="certCount">
            {certificates ? certificates.length || 0 : 'Loading...'}
          </span>
        </p>
        <p>
          Users:{' '}
          <span id="userCount">{users ? users.length || 0 : 'Loading...'}</span>
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
