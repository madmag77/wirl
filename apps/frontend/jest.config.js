export default {
  testEnvironment: 'jest-environment-jsdom',
  transform: {
    '^.+\\.(js|jsx)$': 'babel-jest'
  },
  moduleNameMapper: {
    '\\.(css)$': 'identity-obj-proxy'
  },
  moduleFileExtensions: ['js', 'jsx'],
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js']
};
