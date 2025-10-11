import { useEffect, type FC } from 'react';
import { useForm } from 'react-hook-form';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
} from '@heroui/react';
import type { CreateServerForm } from '../../types';
import { getServer } from '../../duck/api';
import { useAppDispatch } from '../../../../common/hooks';
import { updateServer } from '../../duck';

export interface ServerEditProps {
  serverId: string;
  isOpen: boolean;
  onOpenChange: () => void;
}

export const ServerEdit: FC<ServerEditProps> = (props) => {
  const dispatch = useAppDispatch();
  const { serverId, isOpen, onOpenChange } = props;
  const { register, handleSubmit, reset } = useForm<CreateServerForm>();

  useEffect(() => {
    getServer(serverId).then((response) => {
      const { data } = response;
      reset({
        ...data,
        grpc_port: String(data.grpc_port),
      });
    });
  }, [serverId]);

  const onSubmit = (values: CreateServerForm) => {
    const data = {
      ...values,
      grpc_port: parseInt(values.grpc_port),
    };

    dispatch(
      updateServer({
        id: serverId,
        server: data,
      }),
    ).then(() => {

      onOpenChange();
    });
  };

  return (
    <Modal isOpen={isOpen} onOpenChange={onOpenChange}>
      <form onSubmit={handleSubmit(onSubmit)}>
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex flex-col gap-1">
                Modal Title
              </ModalHeader>
              <ModalBody>
                <div className="form-group">
                  <label>Name:</label>
                  <input {...register('name', { required: true })} />
                </div>
                <div className="form-group">
                  <label>Hostname:</label>
                  <input {...register('hostname', { required: true })} />
                </div>
                <div className="form-group">
                  <label>gRPC Port:</label>
                  <input
                    type="number"
                    {...register('grpc_port', { required: true })}
                  />
                </div>
              </ModalBody>
              <ModalFooter>
                <Button color="primary" type="submit">
                  Save
                </Button>
                <Button color="danger" variant="light" onPress={onClose}>
                  Close
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </form>
    </Modal>
  );
};
