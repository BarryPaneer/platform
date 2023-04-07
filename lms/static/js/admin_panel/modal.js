const template = /* @html */`
<div :class="'wrapper wrapper-modal-window wrapper-modal-window-' + name" role="dialog">
    <div class="modal-window-overlay"></div>
    <div :class="'modal-window modal-' + size" tabindex="-1">
        <div :class="name + '-modal'">
            <slot name="header">
                <div class="modal-header">
                    <h2 id="modal-window-title" class="title modal-window-title" v-if="title">
                        <span>{{ title }}</span>
                    </h2>

                    <span v-if="displayCloseButton" class="icon-close" @click="close"><i class="far fa-times"></i></span>
                </div>
            </slot>

            <div class="modal-content">
                <slot></slot>
            </div>

            <slot name="footer">
                <div class="modal-actions">
                    <ul>
                        <li class="action-item" v-if="cancelText">
                            <a :disabled="buttonDisabled" href="javascript:void(0)" class="button  action-cancel" @click="!buttonDisabled && close()">{{ gettext(cancelText) }}</a>
                        </li>
                        <li class="action-item" v-if="confirmText">
                            <a :disabled="buttonDisabled" href="javascript:void(0)" class="button  action-primary" @click="!buttonDisabled && confirm()">{{ gettext(confirmText) }}</a>
                        </li>
                    </ul>
                </div>
            </slot>
        </div>
    </div>
</div>
`

Vue.component('modal', {
    template,
    props: {
        name: {
            type: String,
            default: 'modal',
        },
        size: {
            type: String,
            default: 'med', // sm/med/lg
        },
        title: {
            type: String,
            defualt: '',
        },
        displayCloseButton: {
            type: Boolean,
            default: false,
        },
        cancelText: {
            type: String,
            default: 'Cancel',
        },
        confirmText: {
            type: String,
            default: 'Confirm',
        },
        buttonDisabled: {
            type: Boolean,
            default: false,
        }
    },
    mounted () {
        document.body.appendChild(this.$el)
        const $modal = this.$el.querySelector('.modal-window')
        const clamp = (x, min = -Infinity, max = Infinity) => Math.min(Math.max(min, x), max)
        if ($modal) {
            const top = window.scrollY + clamp(window.innerHeight - $modal.getBoundingClientRect().height, 0) * 0.3
            $modal.style.top = top + 'px'
        }
    },
    methods: {
        close () {
            this.$emit('close')
        },
        confirm () {
            this.$emit('confirm')
        },
        gettext: window.gettext || (v => v),
    }
})
