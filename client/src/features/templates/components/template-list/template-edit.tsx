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
import type { EditTemplateForm } from '../../types';
import { useAppDispatch } from '../../../../common/hooks';
import { getTemplateById } from '../../duck/api';
import { protocolOptions } from '../add-template/util';
import { updateTemplate } from '../../duck';

export interface TemplateEditProps {
  templateId: string;
  isOpen: boolean;
  onOpenChange: () => void;
}

export const TemplateEdit: FC<TemplateEditProps> = (props) => {
  const dispatch = useAppDispatch();
  const { templateId, isOpen, onOpenChange } = props;
  const { register, handleSubmit, reset } = useForm<EditTemplateForm>();

  useEffect(() => {
    getTemplateById(templateId).then((response) => {
      const { data } = response;
      reset({
        ...data,
        default_port: String(data.default_port),
      });
    });
  }, [templateId]);

  const onSubmit = (values: EditTemplateForm) => {
    const data = {
      ...values,
      default_port: parseInt(values.default_port),
    };

    dispatch(
      updateTemplate({
        id: templateId,
        template: data,
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
                <div>
                  <div className="form-group">
                    <label>Name:</label>
                    <input
                      type="text"
                      {...register('name', { required: true })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Protocol:</label>
                    <select
                      id="editProtocol"
                      {...register('protocol', { required: true })}
                    >
                      {Object.entries(protocolOptions).map((protocolTupple) => (
                        <option value={protocolTupple[0]}>
                          {protocolTupple[1]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Default Port:</label>
                    <input
                      type="number"
                     {...register('default_port', {required: true})}
                    />
                  </div>
                  <div className="form-group">
                    <label>
                      <input type="checkbox" {...register('requires_tls')} />{' '}
                      Requires TLS
                    </label>
                  </div>
                  <div className="form-group">
                    <label>
                      <input type="checkbox" {...register('is_active')} />{' '}
                      Active
                    </label>
                  </div>
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
