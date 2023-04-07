import React from "react";

class ProgressRing extends React.Component {
    constructor(props) {
        super(props);

        this.ref0 = React.createRef()
        this.state = {
            offset: 0
        }
    }

    componentDidMount() {
        const {value} = this.props, pr = this.props, element = this.ref0.current
        var progressRing = this.ref0.current,
            circle = element.querySelector('.progress-ring__circle'),
            circleBg = element.querySelector('.progress-ring__circle-bg'),
            step = element.querySelector('.step'),
            radius = circle.r.baseVal.value,
            size = (radius + 7) * 2,
            circumference = radius * 2 * Math.PI,
            offset = pr.step ? circumference - value / pr.step * circumference : circumference - value / 100 * circumference;
        progressRing.style.height = size + "px";
        progressRing.style.width = size + "px";
        progressRing.style.strokeDasharray = circumference + " " + circumference;
        circle.style.strokeDashoffset = offset;
        circle.style.transformOrigin = (radius + 7) + "px " + (radius + 7) + "px";
        if (pr.strokeWidth) {
            circle.style.strokeWidth=pr.strokeWidth
            circleBg.style.strokeWidth=pr.strokeWidth
        }
    }

    render() {
        const {value, radius=12, className} = this.props, pr=this.props
        return <div className={`progress-ring0 ${className?className:''}`}>
            {<svg ref={this.ref0} className="progress-ring">
                <circle className="progress-ring__circle-bg" r={radius} cx={radius+8} cy={radius+9} />
                <circle className="progress-ring__circle" r={radius} cx={radius+5} cy={radius+8} />
            </svg>}
            {typeof(pr.step)!='number' && <div>
                <span className="percent">{value}%</span>
            </div>}
            {typeof(pr.step)=='number' && <span className="step">{pr.value +'/'+ pr.step}</span>}
        </div>
    }
}

export {ProgressRing}

