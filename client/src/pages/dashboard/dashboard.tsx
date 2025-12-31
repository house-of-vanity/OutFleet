import type { RouteObject } from 'react-router';
import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../common/hooks';
import {
  fetchServers,
  getServersState,
  fetchTemplates,
  getTemplatesState,
  fetchUsers,
  getUsersState,
  getCertificatesState,
  fetchCertificates,
} from '../../features';

export const Dashboard = () => {
  const dispatch = useAppDispatch();
  const { loading: serverLoading, servers } = useAppSelector(getServersState);
  const { loading: usersLoading, users } = useAppSelector(getUsersState);
  const { loading: certificatesLoading, certificates } =
    useAppSelector(getCertificatesState);
  const { loading: templatesLoading, templates } =
    useAppSelector(getTemplatesState);

  useEffect(() => {
    dispatch(fetchServers());
    dispatch(fetchTemplates());
    dispatch(fetchUsers());
    dispatch(fetchCertificates());
  }, [dispatch]);

  return (
    <div id="dashboard" className="tab-content active">
      <div className="section">
        <h2>Statistics</h2>
        <p>
          Servers:{' '}
          <span id="serverCount">
            {serverLoading === true && 'Loading...'}
            {servers && String(servers.length)}
          </span>
        </p>
        <p>
          Templates:{' '}
          <span id="templateCount">
            {templatesLoading && 'Loading...'}
            {templates && String(templates.length)}
          </span>
        </p>
        <p>
          Certificates:{' '}
          <span id="certCount">
            {certificatesLoading && 'Loading...'}
            {certificates && String(certificates.length)}
          </span>
        </p>
        <p>
          Users:{' '}
          <span id="userCount">
            {usersLoading && 'Loading...'}
            {users && String(users.length)}
          </span>
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
