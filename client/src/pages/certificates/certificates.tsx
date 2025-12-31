import type { RouteObject } from 'react-router';
import { useAppDispatch, useAppSelector } from '../../common/hooks';
import { useEffect } from 'react';
import { fetchCertificates, getCertificatesState } from '../../features';
import { CreateCertificate } from '../../features/certificates';
import { CertificateList } from '../../features/certificates/components/certificate-list';

export const Certificates = () => {
  const dispatch = useAppDispatch()

  const { loading, certificates } = useAppSelector(getCertificatesState)

  useEffect(()=>{
    dispatch(fetchCertificates())
  }, [dispatch])

  return (
    <div id="certificates" className="tab-content active">
      <div className="section">
        <h2>Add Certificate</h2>
        <CreateCertificate/>
      </div>

      <div className="section">
        <h2>Certificates List</h2>
        <div id="certificatesList" className="loading">
          { loading && 'Loading...' }
          { certificates.length ? <CertificateList certificates={certificates}/> : <p>No certificates found</p> }
        </div>
      </div>
    </div>
  );
};

export const CertificatesRoute: RouteObject = {
  path: '/certificates',
  Component: Certificates,
};
