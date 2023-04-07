/* Multi-language initialisation for the jQuery UI date picker plugin. */
/* Written by Aaron Zhao */
/* In the future if we need more language translations, find in this page https://github.com/jquery/jquery-ui/tree/master/ui/i18n */

( function( factory ) {
	if ( typeof define === "function" && define.amd ) {

		// AMD. Register as an anonymous module.
		define( [ "../widgets/datepicker" ], factory );
	} else {

		// Browser globals
		factory( jQuery.datepicker );
	}
}( function( datepicker ) {

datepicker.regional.fr = {
	closeText: "Fermer",
	prevText: "Précédent",
	nextText: "Suivant",
	currentText: "Aujourd'hui",
	monthNames: [ "janvier", "février", "mars", "avril", "mai", "juin",
		"juillet", "août", "septembre", "octobre", "novembre", "décembre" ],
	monthNamesShort: [ "janv.", "févr.", "mars", "avr.", "mai", "juin",
		"juil.", "août", "sept.", "oct.", "nov.", "déc." ],
	dayNames: [ "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi" ],
	dayNamesShort: [ "dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam." ],
	dayNamesMin: [ "D","L","M","M","J","V","S" ],
	weekHeader: "Sem.",
	dateFormat: "dd/mm/yy",
	firstDay: 1,
	isRTL: false,
	showMonthAfterYear: false,
	yearSuffix: "" };

datepicker.regional.ro = {
	closeText: "Închide",
	prevText: "&#xAB; Luna precedentă",
	nextText: "Luna următoare &#xBB;",
	currentText: "Azi",
	monthNames: [ "Ianuarie","Februarie","Martie","Aprilie","Mai","Iunie",
	"Iulie","August","Septembrie","Octombrie","Noiembrie","Decembrie" ],
	monthNamesShort: [ "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
	"Iul", "Aug", "Sep", "Oct", "Nov", "Dec" ],
	dayNames: [ "Duminică", "Luni", "Marţi", "Miercuri", "Joi", "Vineri", "Sâmbătă" ],
	dayNamesShort: [ "Dum", "Lun", "Mar", "Mie", "Joi", "Vin", "Sâm" ],
	dayNamesMin: [ "Du","Lu","Ma","Mi","Jo","Vi","Sâ" ],
	weekHeader: "Săpt",
	dateFormat: "dd.mm.yy",
	firstDay: 1,
	isRTL: false,
	showMonthAfterYear: false,
	yearSuffix: "" };

datepicker.regional[ "zh-cn" ] = {
	closeText: "关闭",
	prevText: "&#x3C;上月",
	nextText: "下月&#x3E;",
	currentText: "今天",
	monthNames: [ "一月","二月","三月","四月","五月","六月",
	"七月","八月","九月","十月","十一月","十二月" ],
	monthNamesShort: [ "一月","二月","三月","四月","五月","六月",
	"七月","八月","九月","十月","十一月","十二月" ],
	dayNames: [ "星期日","星期一","星期二","星期三","星期四","星期五","星期六" ],
	dayNamesShort: [ "周日","周一","周二","周三","周四","周五","周六" ],
	dayNamesMin: [ "日","一","二","三","四","五","六" ],
	weekHeader: "周",
	dateFormat: "yy-mm-dd",
	firstDay: 1,
	isRTL: false,
	showMonthAfterYear: true,
	yearSuffix: "年" };

datepicker.setDefaults( datepicker.regional[$('html')[0].lang] );

return datepicker.regional[$('html')[0].lang];

} ) );
