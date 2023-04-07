import React from 'react'
import Switch from 'react-switch'


export function Switcher ({value, onValueChange}) {
    const [checked, setChecked] = React.useState(value === 'true' || value === true)

    function handleChange(checked) {
        setChecked(checked)
        onValueChange && onValueChange(checked)
    }

    return (
        <Switch onChange={handleChange} checked={checked} width={40}
                checkedIcon={false} uncheckedIcon={false} onColor={"#e7413c"}/>
    )
}

const template = /* @html */`<span></span>`

export default Vue.component('switcher', {
    template,
    props: {
        value: {
            type: Boolean,
            default: false,
        },
    },
    mounted () {
        ReactDOM.render(
            React.createElement(Switcher, {
                value: this.value,
                onValueChange: value => this.$emit('input', value)
            }, null),
            this.$el
        )
    },
    destroyed () {
        ReactDOM.unmountComponentAtNode(this.$el)
    }
})
