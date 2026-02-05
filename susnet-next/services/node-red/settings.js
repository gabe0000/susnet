const adminUser = process.env.NODERED_ADMIN_USER;
const adminPassHash = process.env.NODERED_ADMIN_PASS_HASH;

const settings = {
  uiPort: process.env.PORT || 1880,
  mqttReconnectTime: 15000,
  serialReconnectTime: 15000,
  debugMaxLength: 1000,
  flowFile: 'flows.json',
  credentialSecret: process.env.NODERED_CREDENTIAL_SECRET || 'change-me',
  editorTheme: {
    projects: { enabled: true }
  }
};

if (adminUser && adminPassHash) {
  settings.adminAuth = {
    type: 'credentials',
    users: [{
      username: adminUser,
      password: adminPassHash,
      permissions: '*'
    }]
  };
}

module.exports = settings;
