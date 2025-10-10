import { useEffect } from 'react';
import type { RouteObject } from 'react-router';
import { AddServer } from '../../features/servers/components/add-server/add-server';
import { fetchServers, getServersState } from '../../features';
import { useAppDispatch, useAppSelector } from '../../common/hooks';
import clsx from 'clsx';
import { ServersList } from '../../features/servers/components/servers-list';

export const Servers = () => {
  const dispatch = useAppDispatch();
  const { loading, servers } = useAppSelector(getServersState);

  useEffect(() => {
    dispatch(fetchServers());
  }, [dispatch]);

  return (
    <div id="servers" className="tab-content active">
      <AddServer />

      <div className="section">
        <h2>Servers List</h2>
        <div id="serversList" className={clsx({ loading: loading })}>
          {loading && 'Loading...'}
          {servers.length ? (
            <ServersList servers={servers} />
          ) : (
            <p>No servers found</p>
          )}
        </div>
      </div>
    </div>
  );
};

export const ServersRoute: RouteObject = {
  path: '/servers',
  Component: Servers,
};
