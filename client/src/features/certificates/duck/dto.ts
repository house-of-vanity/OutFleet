export interface CertificateDTO {
  name: string;
  domain: string;
  cert_type: string;
  expires_at: string;
  auto_renew: boolean;
  id: string
  created_at: string
  certificate_pem: string
  has_private_key: boolean
}

export interface CreateCertificateDTO {
  name: string;
  domain: string;
  cert_type: string;
  auto_renew: boolean;
}

export interface EditCertificateDTO {
    name: string
    domain: string
    auto_renew: boolean
}