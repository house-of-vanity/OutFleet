import type { FC } from 'react';
import { useDisclosure } from '@heroui/react';
import { deleteServerAction, type ServerDTO } from '../../duck';
import { testServer } from '../../duck/api';
import { appNotificator } from '../../../../utils/notification/app-notificator';
import { useAppDispatch } from '../../../../common/hooks';
import { ServerEdit } from './server-edit';

export interface ServerViewProps {
  server: ServerDTO;
}

export const ServerView: FC<ServerViewProps> = ({ server }) => {
  const dispatch = useAppDispatch();

  const handleTestServer = () => {
    testServer(server.id).then((result) => {
      const { connected } = result.data;
      appNotificator.add({
        message: connected ? 'Connection OK' : 'Connection failed',
        type: connected ? 'success' : 'error',
      });
    });
  };

  const handleDeleteServer = () => {
    if (confirm('Delete server?')) {
      dispatch(deleteServerAction(server.id));
    }
  };

  const { isOpen, onOpen, onOpenChange } = useDisclosure();

  return (
    <>
      <tr>
        <td>{server.name}</td>
        <td>{server.hostname}</td>
        <td>{server.grpc_port}</td>
        <td>{server.status}</td>
        <td>
          <button className="btn btn-success" onClick={handleTestServer}>
            Test
          </button>
          <button className="btn btn-primary" onClick={onOpen}>
            Edit
          </button>
          <button className="btn btn-danger" onClick={handleDeleteServer}>
            Delete
          </button>
        </td>
      </tr>
      <ServerEdit
        serverId={server.id}
        isOpen={isOpen}
        onOpenChange={onOpenChange}
      />
    </>
  );
};
