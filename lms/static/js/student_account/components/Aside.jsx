import React, {Component} from 'react';

export default class Aside extends Component {
    constructor(props) {
        super(props);
    }

    render() {
        return (
            <aside>
                <figure className="instruction-text">
                    <img src={(this.props.static_url || '/static/images/')+ '/login-illustration.jpg'}/>
                </figure>
            </aside>
        );
    }
}

