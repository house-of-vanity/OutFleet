import type { FC } from 'react';
import type { ServerDTO } from '../../duck';
import { ServerView } from './server-view';

export interface ServersListProps {
  servers: ServerDTO[];
}

export const ServersList: FC<ServersListProps> = (props) => {
  const { servers } = props;

  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Hostname</th>
          <th>Port</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {servers.map((server) => (
          <ServerView key={server.id} server={server} />
        ))}
      </tbody>
    </table>
  );
};
