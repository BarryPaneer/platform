import '../../../common/static/js/vendor/gistfile1'

export class LanguageSelector {

    constructor () {
        let wrapper;
        /* Look for any elements with the class "footer-language-selector": */
        wrapper = document.querySelector(".footer-language-selector");

        let selElmnt = this.selectEl = wrapper.querySelector('select');
        /* For each element, create a new DIV that will act as the selected item: */
        let dropdown = this.dropdown = document.createElement("div");
        dropdown.setAttribute("class", "select-selected");
        let icon = document.createElement("i");
        icon.setAttribute("class", "far fa-globe");

        let span = document.createElement("span");
        dropdown.appendChild(icon);
        dropdown.appendChild(span);
        let selectedItem = selElmnt.children[selElmnt.selectedIndex];
        span.innerText = selectedItem.innerText;
        wrapper.appendChild(dropdown);

        /* For each element, create a new DIV that will contain the option list: */
        let panel = this.panel = document.createElement("ul");
        panel.setAttribute("class", "select-items select-hide");
        let selectedIndex = this.selectEl.selectedIndex;

        for (let j = 0; j < selElmnt.length; j++) {
            /* For each option in the original select element,
            create a new DIV that will act as an option item: */
            let item = document.createElement("li");
            let span = document.createElement("span");
            item.appendChild(span);
            const option = selElmnt.options[j];
            span.innerText = option.innerHTML;

            if (j == selectedIndex){
                item.classList.add('same-as-selected');
                item.setAttribute("style", "display: none;");

            }

            item.addEventListener("click", this.selectItem.bind(this));
            panel.appendChild(item);
        }
        wrapper.appendChild(panel);

        dropdown.addEventListener("click", this.togglePanel.bind(this));
        document.querySelector('body:not(.select-component)').addEventListener("click", this.closePanel.bind(this));
    }

    togglePanel(e) {
        /* When the select box is clicked, close any other select boxes,
        and open/close the current select box: */
        e && e.stopPropagation();
        this.closeAllSelect(this.dropdown);
        this.dropdown.nextSibling.classList.toggle("select-hide");
        this.dropdown.classList.toggle("select-arrow-active");
    }

    closePanel() {
        this.closeAllSelect(this.dropdown);
        this.dropdown.nextSibling.classList.add("select-hide");
        this.dropdown.classList.remove("select-arrow-active");
    }

    selectItem (e) {
        /* When an item is clicked, update the original select box,
        and the selected item: */
        let span = this.dropdown.querySelector('span');
        let li = e.currentTarget;
        let liSpan = li.querySelector('span');

        span.innerText = liSpan.innerText;
        //this.panel.querySelector('li').classList.remove('same-as-selected');
        this.panel.querySelectorAll('li').forEach(li=> {
            li.classList.remove('same-as-selected');
            li.setAttribute("style", "display: block;");
    }
        )
        li.classList.add('same-as-selected');
        li.setAttribute("style", "display: none;");
        this.togglePanel();
        this.selectEl.selectedIndex = this.getIndex(li);
        footerLanguageSelector.handleSelection(this.selectEl);
    }

    closeAllSelect(elmnt) {
        /* A function that will close all select boxes in the document,
        except the current select box: */
        let panel, dropdown, arrNo = [];
        panel = document.getElementsByClassName("select-items");
        dropdown = document.getElementsByClassName("select-selected");
        for (let i = 0; i < dropdown.length; i++) {
            if (elmnt == dropdown[i]) {
                arrNo.push(i)
            } else {
                dropdown[i].classList.remove("select-arrow-active");
            }
        }
        for (let i = 0; i < panel.length; i++) {
            if (arrNo.indexOf(i)) {
                x[i].classList.add("select-hide");
            }
        }
    }

    getIndex(liRef) {
        let nodes = Array.prototype.slice.call( this.panel.children );
        return nodes.indexOf( liRef );
    }
}
