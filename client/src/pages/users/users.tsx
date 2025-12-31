import type { RouteObject } from 'react-router';

export const Users = () => {
  return (
    <div id="users" className="tab-content active">
      <div className="section">
        <h2>Add User</h2>
        <form id="userForm">
          <div className="form-group">
            <label>Name:</label>
            <input type="text" id="userName" required />
          </div>
          <div className="form-group">
            <label>Comment:</label>
            <input type="text" id="userComment" />
          </div>
          <div className="form-group">
            <label>Telegram ID:</label>
            <input type="number" id="userTelegram" />
          </div>
          <button type="submit" className="btn btn-primary">
            Add User
          </button>
        </form>
      </div>

      <div className="section">
        <h2>Users List</h2>
        <div id="usersList" className="loading">
          Loading...
        </div>
      </div>
    </div>
  );
};

export const UsersRoute: RouteObject = {
  path: '/users',
  Component: Users,
};
