import type { FC } from 'react';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
} from '@heroui/react';
import type { CertificateDTO } from '../../duck';

export interface CertificateDetailProps {
  cetificate: CertificateDTO;
  isOpen: boolean;
  onOpenChange: () => void;
}

export const CertificateDetail: FC<CertificateDetailProps> = (props) => {
  const { cetificate, isOpen, onOpenChange } = props;
  return (
    <Modal isOpen={isOpen} onOpenChange={onOpenChange}>
      <ModalContent>
        {(onClose) => (
          <>
            <ModalHeader className="flex flex-col gap-1">
              Modal Title
            </ModalHeader>
            <ModalBody>
              <div>
                <h4>Basic Information</h4>
                <p>
                  <strong>Name:</strong> ${cetificate.name}
                </p>
                <p>
                  <strong>Domain:</strong> ${cetificate.domain}
                </p>
                <p>
                  <strong>Type:</strong> ${cetificate.cert_type}
                </p>
                <p>
                  <strong>Auto Renew:</strong>
                  {cetificate.auto_renew ? 'Yes' : 'No'}
                </p>
                <p>
                  <strong>Created:</strong>
                  {new Date(cetificate.created_at).toLocaleString()}
                </p>
                <p>
                  <strong>Expires:</strong>
                  {new Date(cetificate.expires_at).toLocaleString()}
                </p>

                <h4>Certificate PEM</h4>
                <div className="cert-details">
                  {cetificate.certificate_pem || 'Not available'}
                </div>

                <h4>Private Key</h4>
                <div className="cert-details">
                  {cetificate.has_private_key
                    ? '[Hidden for security]'
                    : 'Not available'}
                </div>
              </div>
            </ModalBody>
            <ModalFooter>
              <Button color="danger" variant="light" onPress={onClose}>
                Close
              </Button>
            </ModalFooter>
          </>
        )}
      </ModalContent>
    </Modal>
  );
};
