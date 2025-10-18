import type { FC } from 'react';
import { deleteCertificateAction, type CertificateDTO } from '../../duck';
import { useDisclosure } from '@heroui/react';
import { CertificateDetail } from './certificate-details';
import { CertificateEdit } from './certificate-edit';
import { useAppDispatch } from '../../../../common/hooks';

export interface CertificateViewProps {
  certificate: CertificateDTO;
}

export const CertificateView: FC<CertificateViewProps> = ({ certificate }) => {
    const dispatch = useAppDispatch()
  const detailDisclosure = useDisclosure();
  const editDisclosure = useDisclosure();

  const handleDeleteCertificate = () => {
    if (confirm('Delete certificate?')) {
      dispatch(deleteCertificateAction(certificate.id));
    }
  };

  return (
    <>
      <tr>
        <td>{certificate.name}</td>
        <td>{certificate.domain}</td>
        <td>{certificate.cert_type}</td>
        <td>{new Date(certificate.expires_at).toLocaleDateString()}</td>
        <td>{certificate.auto_renew ? 'Yes' : 'No'}</td>
        <td>
          <button
            className="btn btn-secondary"
            onClick={detailDisclosure.onOpenChange}
          >
            View
          </button>
          <button
            className="btn btn-primary"
            onClick={editDisclosure.onOpenChange}
          >
            Edit
          </button>
          <button
            className="btn btn-danger"
            onClick={handleDeleteCertificate}
          >
            Delete
          </button>
        </td>
      </tr>
      <CertificateDetail cetificate={certificate} {...detailDisclosure} />
      <CertificateEdit {...editDisclosure} certificateId={certificate.id} />
    </>
  );
};
