/* eslint-env node */

'use strict';

var path = require('path');
var webpack = require('webpack');
var BundleTracker = require('webpack-bundle-tracker');
var StringReplace = require('string-replace-webpack-plugin');
var Merge = require('webpack-merge');

var files = require('./webpack-config/file-lists.js');
var xmoduleJS = require('./common/static/xmodule/webpack.xmodule.config.js');

var filesWithRequireJSBlocks = [
    path.resolve(__dirname, 'common/static/common/js/components/utils/view_utils.js'),
    /descriptors\/js/,
    /modules\/js/,
    /common\/lib\/xmodule\/xmodule\/js\/src\//
];

var defineHeader = /\(function ?\(((define|require|requirejs|\$)(, )?)+\) ?\{/;
var defineCallFooter = /\}\)\.call\(this, ((define|require)( \|\| RequireJS\.(define|require))?(, )?)+?\);/;
var defineDirectFooter = /\}\(((window\.)?(RequireJS\.)?(requirejs|define|require|jQuery)(, )?)+\)\);/;
var defineFancyFooter = /\}\).call\(\s*this(\s|.)*define(\s|.)*\);/;
var defineFooter = new RegExp('(' + defineCallFooter.source + ')|('
                             + defineDirectFooter.source + ')|('
                             + defineFancyFooter.source + ')', 'm');

module.exports = Merge.smart({
    context: __dirname,

    entry: {
        // Studio
        Import: ['babel-polyfill', './cms/static/js/features/import/factories/import.js'],
        CourseOrLibraryListing: ['babel-polyfill', './cms/static/js/features_jsx/studio/CourseOrLibraryListing.jsx'],
        'js/factories/login': ['babel-polyfill', './cms/static/js/factories/login.js'],
        'js/factories/textbooks': ['babel-polyfill', './cms/static/js/factories/textbooks.js'],
        'js/factories/container': ['babel-polyfill', './cms/static/js/factories/container.js'],
        'js/factories/context_course': './cms/static/js/factories/context_course.js',
        'js/factories/library': ['babel-polyfill', './cms/static/js/factories/library.js'],
        'js/factories/xblock_validation': ['babel-polyfill', './cms/static/js/factories/xblock_validation.js'],
        'js/factories/edit_tabs': ['babel-polyfill', './cms/static/js/factories/edit_tabs.js'],
        'js/question_mark': ['babel-polyfill', './cms/static/js/question_mark.js'],
        'js/switcher': ['babel-polyfill', './cms/static/js/switcher.js'],
        'js/sock': ['babel-polyfill', './cms/static/js/sock.js'],
        'js/checklists': ['babel-polyfill', './cms/static/js/checklists.js'],

        LanguageSelector: './cms/static/js/language_selector.js',
        MyCourses: ['babel-polyfill', './lms/static/js/MyCourses.js'],

        // LMS
        SingleSupportForm: ['babel-polyfill', './lms/static/support/jsx/single_support_form.jsx'],
        AlertStatusBar: ['babel-polyfill', './lms/static/js/accessible_components/StatusBarAlert.jsx'],
        LearnerAnalyticsDashboard: ['babel-polyfill', './lms/static/js/learner_analytics_dashboard/LearnerAnalyticsDashboard.jsx'],
        UpsellExperimentModal: ['babel-polyfill', './lms/static/common/js/components/UpsellExperimentModal.jsx'],
        PortfolioExperimentUpsellModal: ['babel-polyfill', './lms/static/common/js/components/PortfolioExperimentUpsellModal.jsx'],
        EntitlementSupportPage: ['babel-polyfill', './lms/djangoapps/support/static/support/jsx/entitlements/index.jsx'],
        PasswordResetConfirmation: ['babel-polyfill', './lms/static/js/student_account/components/PasswordResetConfirmation.jsx'],
        QuestionMark: ['babel-polyfill', './lms/static/js/QuestionMark.js'],
        NumberLocale: ['babel-polyfill', './lms/static/js/NumberLocale.js'],
        VueraSwitcher: ['babel-polyfill', './lms/static/js/admin_panel/vuera-switcher.js'],
        BatchEnrollment: './lms/static/js/admin_panel/batch_enrollment.jsx',

        PasswordCreateConfirmation: ['babel-polyfill', './lms/static/js/student_account/components/PasswordCreateConfirmation.jsx'],
        StudentAccountDeletion: ['babel-polyfill', './lms/static/js/student_account/components/StudentAccountDeletion.jsx'],
        LeaderBoard: ['babel-polyfill', './lms/static/js/triboo_analytics/LeaderBoard.js'],
        StudentAccountDeletionInitializer: ['babel-polyfill', './lms/static/js/student_account/StudentAccountDeletionInitializer.js'],

        Dialog: ['babel-polyfill', './lms/static/js/dialog.js'],
        Dashboard: ['babel-polyfill', './lms/static/js/dashboard.js'],
        Courseware: ['babel-polyfill', './lms/static/js/courseware.js'],

        // Learner Dashboard
        EntitlementFactory: ['babel-polyfill', './lms/static/js/learner_dashboard/course_entitlement_factory.js'],
        EntitlementUnenrollmentFactory: ['babel-polyfill', './lms/static/js/learner_dashboard/entitlement_unenrollment_factory.js'],
        ProgramDetailsFactory: ['babel-polyfill', './lms/static/js/learner_dashboard/program_details_factory.js'],
        ProgramListFactory: ['babel-polyfill', './lms/static/js/learner_dashboard/program_list_factory.js'],
        UnenrollmentFactory: ['babel-polyfill', './lms/static/js/learner_dashboard/unenrollment_factory.js'],
        CompletionOnViewService: ['babel-polyfill', './lms/static/completion/js/CompletionOnViewService.js'],
        EdflexCatalogCourses: ['babel-polyfill', './lms/static/js/external_catalog/EdflexCatalogCourses.jsx'],
        CrehanaCatalogCourses: ['babel-polyfill', './lms/static/js/external_catalog/CrehanaCatalogCourses.jsx'],
        CoursesOverview: ['babel-polyfill', './lms/static/js/programs/overview.jsx'],
        CatalogPrograms: ['babel-polyfill', './lms/static/js/programs/catalog_programs.jsx'],
        ProgramEntrance: ['babel-polyfill', './lms/static/js/programs/program_entrance.js'],
        MyTrainingOverview: ['babel-polyfill', './lms/static/js/my_training/overview.jsx'],
        MyTrainingPrograms: ['babel-polyfill', './lms/static/js/my_training/programs.jsx'],

        ExternalCatalogOverview: ['babel-polyfill', './lms/static/js/external_catalog/ExternalCatalogOverview.jsx'],

        //AndersPink Integration
        AndersPinkCatalogArticles : ['babel-polyfill', './lms/static/js/external_catalog/AndersPinkCatalog/AndersPinkCatalogArticles.jsx'],
        AnderspinkBoardArticles :['babel-polyfill', './lms/static/js/external_catalog/AndersPinkCatalog/AnderspinkBoardArticles.jsx'],
        // Features
        CourseGoals: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/CourseGoals.js'],
        CourseHome: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/CourseHome.js'],
        CourseOutline: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/CourseOutline.js'],
        CourseSock: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/CourseSock.js'],
        CourseTalkReviews: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/CourseTalkReviews.js'],
        Currency: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/currency.js'],
        Enrollment: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/Enrollment.js'],
        LatestUpdate: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/LatestUpdate.js'],
        WelcomeMessage: ['babel-polyfill', './openedx/features/course_experience/static/course_experience/js/WelcomeMessage.js'],

        CookiePolicyBanner: ['babel-polyfill', './common/static/js/src/CookiePolicyBanner.jsx'],

        // Triboo Analytics
        Toolbar: ['./lms/static/js/triboo_analytics/Toolbar.js'],
        CourseReport: ['babel-polyfill', './lms/static/js/triboo_analytics/CourseReport.js'],
        LearnerReport: ['babel-polyfill', './lms/static/js/triboo_analytics/LearnerReport.js'],
        ILTGlobalReport: ['./lms/static/js/triboo_analytics/ILTGlobalReport.js'],
        ILTLearnerReport: ['babel-polyfill', './lms/static/js/triboo_analytics/ILTLearnerReport.js'],
        ILTReport: ['babel-polyfill', './lms/static/js/triboo_analytics/ILTReport.js'],
        Transcript: ['babel-polyfill', './lms/static/js/triboo_analytics/Transcript.js'],
        CustomizedReport: ['babel-polyfill', './lms/static/js/triboo_analytics/CustomizedReport.js'],

        // Common
        ReactRenderer: ['babel-polyfill', './common/static/js/src/ReactRenderer.jsx'],
        XModuleShim: ['babel-polyfill', 'xmodule/js/src/xmodule.js'],

        VerticalStudentView: ['babel-polyfill', './common/lib/xmodule/xmodule/assets/vertical/public/js/vertical_student_view.js']
    },

    output: {
        path: path.resolve(__dirname, 'common/static/bundles'),
        libraryTarget: 'window'
    },

    plugins: [
        new webpack.NoEmitOnErrorsPlugin(),
        new webpack.NamedModulesPlugin(),
        new BundleTracker({
            path: process.env.STATIC_ROOT_CMS,
            filename: 'webpack-stats.json'
        }),
        new BundleTracker({
            path: process.env.STATIC_ROOT_LMS,
            filename: 'webpack-stats.json'
        }),
        new webpack.ProvidePlugin({
            fetch: 'imports-loader?this=>global!exports-loader?global.fetch!whatwg-fetch',
            _: 'underscore',
            $: 'jquery',
            jQuery: 'jquery',
            'window.jQuery': 'jquery',
            Popper: 'popper.js', // used by bootstrap
            CodeMirror: 'codemirror',
            'edx.HtmlUtils': 'edx-ui-toolkit/js/utils/html-utils',
            AjaxPrefix: 'ajax_prefix'
        }),

        // Note: Until karma-webpack releases v3, it doesn't play well with
        // the CommonsChunkPlugin. We have a kludge in karma.common.conf.js
        // that dynamically removes this plugin from webpack config when
        // running those tests (the details are in that file). This is a
        // recommended workaround, as this plugin is just an optimization. But
        // because of this, we really don't want to get too fancy with how we
        // invoke this plugin until we can upgrade karma-webpack.
        new webpack.optimize.CommonsChunkPlugin({
            // If the value below changes, update the render_bundle call in
            // common/djangoapps/pipeline_mako/templates/static_content.html
            name: 'commons',
            filename: 'commons.js',
            minChunks: 3
        })
    ],

    module: {
        noParse: [
            // See sinon/webpack interaction weirdness:
            // https://github.com/webpack/webpack/issues/304#issuecomment-272150177
            // (I've tried every other suggestion solution on that page, this
            // was the only one that worked.)
            /\/sinon\.js|codemirror-compressed\.js|hls\.js|tinymce\.full\.min\.js/
        ],
        rules: [
            {
                test: files.namespacedRequire.concat(files.textBangUnderscore, filesWithRequireJSBlocks),
                loader: StringReplace.replace(
                    ['babel-loader'],
                    {
                        replacements: [
                            {
                                pattern: defineHeader,
                                replacement: function() { return ''; }
                            },
                            {
                                pattern: defineFooter,
                                replacement: function() { return ''; }
                            },
                            {
                                pattern: /(\/\* RequireJS) \*\//g,
                                replacement: function(match, p1) { return p1; }
                            },
                            {
                                pattern: /\/\* Webpack/g,
                                replacement: function(match) { return match + ' */'; }
                            },
                            {
                                pattern: /text!(.*?\.underscore)/g,
                                replacement: function(match, p1) { return p1; }
                            },
                            {
                                pattern: /RequireJS.require/g,
                                replacement: function() {
                                    return 'require';
                                }
                            }
                        ]
                    }
                )
            },
            {
                test: /\.(js|jsx)$/,
                exclude: [
                    /node_modules/,
                    files.namespacedRequire,
                    files.textBangUnderscore,
                    filesWithRequireJSBlocks
                ],
                // use: 'babel-loader'
                use: {
                    loader: 'babel-loader',
                    options: {
                        // presets:['@babel/preset-env']
                    }
                }
            },
            {
                test: /\.(js|jsx)$/,
                include: [
                    /paragon/
                ],
                use: 'babel-loader'
            },
            {
                test: path.resolve(__dirname, 'common/static/js/src/ajax_prefix.js'),
                use: [
                    'babel-loader',
                    {
                        loader: 'exports-loader',
                        options: {
                            'this.AjaxPrefix': true
                        }
                    }
                ]
            },
            {
                test: /\.underscore$/,
                use: 'raw-loader'
            },
            {
                // This file is used by both RequireJS and Webpack and depends on window globals
                // This is a dirty hack and shouldn't be replicated for other files.
                test: path.resolve(__dirname, 'cms/static/cms/js/main.js'),
                loader: StringReplace.replace(
                    ['babel-loader'],
                    {
                        replacements: [
                            {
                                pattern: /\(function\(AjaxPrefix\) {/,
                                replacement: function() { return ''; }
                            },
                            {
                                pattern: /], function\(domReady, \$, str, Backbone, gettext, NotificationView\) {/,
                                replacement: function() {
                                    // eslint-disable-next-line
                                    return '], function(domReady, $, str, Backbone, gettext, NotificationView, AjaxPrefix) {';
                                }
                            },
                            {
                                pattern: /'..\/..\/common\/js\/components\/views\/feedback_notification',/,
                                replacement: function() {
                                    return "'../../common/js/components/views/feedback_notification', 'AjaxPrefix',";
                                }
                            },
                            {
                                pattern: /}\).call\(this, AjaxPrefix\);/,
                                replacement: function() { return ''; }
                            },
                            {
                                pattern: /'..\/..\/common\/js\/components\/views\/feedback_notification',/,
                                replacement: function() {
                                    return "'../../common/js/components/views/feedback_notification', 'AjaxPrefix',";
                                }
                            }
                        ]
                    }
                )
            },
            {
                test: /\.(woff2?|ttf|eot)(\?v=\d+\.\d+\.\d+)?$/,
                loader: 'file-loader'
            },
            {
                test: /\.svg$/,
                loader: 'svg-inline-loader'
            },
            {
                test: /\.gif$/,
                use: ['file-loader']
            },
            {
                test: /xblock\/core/,
                loader: 'exports-loader?window.XBlock!imports-loader?jquery,jquery.immediateDescendents,this=>window'
            },
            {
                test: /xblock\/runtime.v1/,
                loader: 'exports-loader?window.XBlock!imports-loader?XBlock=xblock/core,this=>window'
            },
            {
                test: /descriptors\/js/,
                loader: 'imports-loader?this=>window'
            },
            {
                test: /modules\/js/,
                loader: 'imports-loader?this=>window'
            },
            {
                test: /codemirror/,
                loader: 'exports-loader?window.CodeMirror'
            },
            {
                test: /tinymce/,
                loader: 'imports-loader?this=>window'
            },
            {
                test: /xmodule\/js\/src\/xmodule/,
                loader: 'exports-loader?window.XModule!imports-loader?this=>window'
            },
            {
                test: /mock-ajax/,
                loader: 'imports-loader?exports=>false'
            },
            {
                test: /d3.min/,
                use: [
                    'babel-loader',
                    {
                        loader: 'exports-loader',
                        options: {
                            d3: true
                        }
                    }
                ]
            },
            {
                test: /logger/,
                loader: 'imports-loader?this=>window'
            }
        ]
    },

    resolve: {
        extensions: ['.js', '.jsx', '.json'],
        alias: {
            AjaxPrefix: 'ajax_prefix',
            accessibility: 'accessibility_tools',
            codemirror: 'codemirror-compressed',
            datepair: 'timepicker/datepair',
            'edx-ui-toolkit': 'edx-ui-toolkit/src/',  // @TODO: some paths in toolkit are not valid relative paths
            ieshim: 'ie_shim',
            jquery: 'jquery/src/jquery',  // Use the non-diqst form of jQuery for better debugging + optimization
            'jquery.flot': 'flot/jquery.flot.min',
            'jquery.ui': 'jquery-ui.min',
            'jquery.tinymce': 'jquery.tinymce.min',
            'jquery.inputnumber': 'html5-input-polyfills/number-polyfill',
            'jquery.qtip': 'jquery.qtip.min',
            'jquery.smoothScroll': 'jquery.smooth-scroll.min',
            'jquery.timepicker': 'timepicker/jquery.timepicker',
            'backbone.associations': 'backbone-associations/backbone-associations-min',
            squire: 'Squire',
            tinymce: 'tinymce.full.min',

            // See sinon/webpack interaction weirdness:
            // https://github.com/webpack/webpack/issues/304#issuecomment-272150177
            // (I've tried every other suggestion solution on that page, this
            // was the only one that worked.)
            sinon: __dirname + '/node_modules/sinon/pkg/sinon.js',
            hls: 'hls.js/dist/hls.js'
        },
        modules: [
            'cms/djangoapps/pipeline_js/js',
            'cms/static',
            'cms/static/cms/js',
            'cms/templates/js',
            'lms/static',
            'common/lib/xmodule',
            'common/lib/xmodule/xmodule/js/src',
            'common/lib/xmodule/xmodule/assets/word_cloud/src/js',
            'common/static',
            'common/static/coffee/src',
            'common/static/common/js',
            'common/static/common/js/vendor/',
            'common/static/js/src',
            'common/static/js/vendor/',
            'common/static/js/vendor/jQuery-File-Upload/js/',
            'common/static/js/vendor/tinymce/js/tinymce',
            'node_modules',
            'common/static/xmodule'
        ]
    },

    resolveLoader: {
        alias: {
            text: 'raw-loader'  // Compatibility with RequireJSText's text! loader, uses raw-loader under the hood
        }
    },

    externals: {
        $: 'jQuery',
        backbone: 'Backbone',
        canvas: 'canvas',
        coursetalk: 'CourseTalk',
        gettext: 'gettext',
        jquery: 'jQuery',
        logger: 'Logger',
        underscore: '_',
        URI: 'URI',
        XBlockToXModuleShim: 'XBlockToXModuleShim',
        XModule: 'XModule'
    },

    watchOptions: {
        poll: true
    },

    node: {
        fs: 'empty'
    }

}, xmoduleJS);
