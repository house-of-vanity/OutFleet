import type { FC } from 'react';
import type { ServerDTO } from '../../duck';

export interface ServersListProps {
  servers: ServerDTO[];
}

export const ServersList: FC<ServersListProps> = (props) => {
  const { servers } = props;

  return (
    <table>
      <tr>
        <th>Name</th>
        <th>Hostname</th>
        <th>Port</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
      {servers.map((s) => (
        <tr>
          <td>{s.name}</td>
          <td>{s.hostname}</td>
          <td>{s.grpc_port}</td>
          <td>{s.status}</td>
          <td>
            <button
              className="btn btn-success"
              // onclick="testServer('${s.id}')"
            >
              Test
            </button>
            <button
              className="btn btn-primary"
              // onclick="editServer('${s.id}')"
            >
              Edit
            </button>
            <button
              className="btn btn-danger"
              // onclick="deleteServer('${s.id}')"
            >
              Delete
            </button>
          </td>
        </tr>
      ))}
    </table>
  );
};
