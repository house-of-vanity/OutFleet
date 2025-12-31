import { Outlet } from 'react-router';
import './home.css';
import { NavMenu } from '../../components/nav-menu/nav-menu';
import { navItems } from './utils';

export const Home = () => {
  return (
    <div>
      <div className="container">
        <h1 className="text-3xl font-bold underline">Xray Admin Panel - Test Interface</h1>

        {/* <!-- Toast notifications container --> */}
        <div className="toast-container" id="toastContainer"></div>

        <NavMenu items={navItems} />
        <Outlet />
      </div>

      {/* <!-- Modal dialogs --> */}
      <div id="editModal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <div className="modal-title" id="editModalTitle">
              Edit Item
            </div>
            <button
              className="modal-close"
              // onClick="closeModal('editModal')"
            >
              &times;
            </button>
          </div>
          <div className="modal-body" id="editModalBody">
            {/* <!-- Content will be dynamically loaded --> */}
          </div>
          <div className="modal-footer">
            <button
              className="btn btn-secondary"
              // onClick="closeModal('editModal')"
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              id="saveEditBtn"
              // onClick="saveEdit()"
            >
              Save
            </button>
          </div>
        </div>
      </div>

      <div id="viewModal" className="modal">
        <div className="modal-content">
          <div className="modal-header">
            <div className="modal-title" id="viewModalTitle">
              View Details
            </div>
            <button
              className="modal-close"
              //onClick="closeModal('viewModal')"
            >
              &times;
            </button>
          </div>
          <div className="modal-body" id="viewModalBody">
            {/* <!-- Content will be dynamically loaded --> */}
          </div>
          <div className="modal-footer">
            <button
              className="btn btn-secondary"
              //   onClick="closeModal('viewModal')"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
