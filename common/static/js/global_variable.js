
let IsDebug=false;

try {
    var config = require('../../../webpack.dev.config.private');
    IsDebug = config.IsDebug;
} catch {}

export {IsDebug}
