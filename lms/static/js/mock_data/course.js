const MockedFacetResult = {
    total: 4,
    results:[
        {
            text:'Language', value:'language',
            items:[
                {text:'English', label:4, value:'en'},
                {text:'French', label:3, value:'fr'},
                {text:'Chinese', label:2, value:'zh-cn'},
            ]
        },
        {
            text:'Tag', value:'tag',
            items:[
                {text:'Online', label:15, value:'online'},
                {text:'Onside', label:3, value:'onside'},
            ]
        },

        {
            text:'Region', value:'region',
            items:[
                {text:'Canada', label:21, value:'ca'},
                {text:'Australia', label:1, value:'au'},
            ]
        },
    ]
}

export {MockedFacetResult}
