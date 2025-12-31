import type { FC } from 'react';
import type { CertificateDTO } from '../../duck';
import { CertificateView } from './certificate-view';

export interface CertificateList {
  certificates: CertificateDTO[];
}

export const CertificateList: FC<CertificateList> = ({ certificates }) => {
  return (
    <table>
      <tr>
        <th>Name</th>
        <th>Domain</th>
        <th>Type</th>
        <th>Expires</th>
        <th>Auto Renew</th>
        <th>Actions</th>
      </tr>
      {certificates
        .map((certificate)=><CertificateView certificate={certificate} key={certificate.id}/>)}
    </table>
  );
};
