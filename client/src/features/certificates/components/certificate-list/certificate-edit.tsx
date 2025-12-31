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
import { useAppDispatch } from '../../../../common/hooks';
import { getCertificate } from '../../duck/api';
import { updateCertificate, type EditCertificateDTO } from '../../duck';

export interface CertificateEditProps {
  certificateId: string;
  isOpen: boolean;
  onOpenChange: () => void;
}

export const CertificateEdit: FC<CertificateEditProps> = (props) => {
  const dispatch = useAppDispatch();
  const { certificateId, isOpen, onOpenChange } = props;
  const { register, handleSubmit, reset } = useForm<EditCertificateDTO>();

  useEffect(() => {
    getCertificate(certificateId).then((response) => {
      const { data } = response;
      reset({
        ...data,
      });
    });
  }, [certificateId]);

  const onSubmit = (values: EditCertificateDTO) => {
    dispatch(
      updateCertificate({
        id: certificateId,
        certificate: values
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
                    <label>Domain:</label>
                    <input
                      type="text"
                      {...register('domain', { required: true })}
                    />
                  </div>
                  <div className="form-group">
                    <label>
                      <input type="checkbox" {...register('auto_renew')} /> Auto
                      Renew
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
