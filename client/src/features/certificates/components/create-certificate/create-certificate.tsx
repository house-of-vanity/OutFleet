import type { FC } from 'react';
import { useForm } from 'react-hook-form';
import { createCertificateAction, type CreateCertificateDTO } from '../../duck';
import { useAppDispatch } from '../../../../common/hooks';

export const CreateCertificate: FC = () => {
  const { handleSubmit, register, reset } = useForm<CreateCertificateDTO>();
  const dispatch = useAppDispatch();

  const onSubmit = (values: CreateCertificateDTO) => {
    dispatch(createCertificateAction(values)).then(() => {
      reset();
    });
  };

  return (
    <form id="certificateForm" onSubmit={handleSubmit(onSubmit)}>
      <div className="form-group">
        <label>Name:</label>
        <input type="text" {...register('name', { required: true })} />
      </div>
      <div className="form-group">
        <label>Domain:</label>
        <input
          type="text"
          placeholder="example.com"
          {...register('domain', { required: true })}
        />
      </div>
      <div className="form-group">
        <label>Certificate Type:</label>
        <select id="certType" {...register('cert_type', { required: true })}>
          <option value="self_signed">Self-Signed</option>
        </select>
      </div>
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            id="certAutoRenew"
            {...register('auto_renew')}
          />{' '}
          Auto Renew
        </label>
      </div>
      <button type="submit" className="btn btn-primary">
        Generate Certificate
      </button>
    </form>
  );
};
