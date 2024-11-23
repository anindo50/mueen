$(document).ready(function () {
  $(".library .nav-links li").click(function () {
    // Remove 'active' class from all li elements
    $(".library .nav-links li").removeClass("active");
    // Add 'active' class to the clicked li element
    $(this).addClass("active");
  });

  $(".toggle-password").click(function () {

    $(this).toggleClass("fa-eye fa-eye-slash");
    var input = $($(this).attr("toggle"));
    if (input.attr("type") == "password") {
      input.attr("type", "text");
    } else {
      input.attr("type", "password");
    }
  });
});


const open_btn = document.querySelector(".open-btn");
const close_btn = document.querySelector(".close-btn");
const nav = document.querySelectorAll(".nav");

open_btn.addEventListener("click", () => {
  nav.forEach((nav_el) => nav_el.classList.add("visible"));
  open_btn.style.display = "none";
  close_btn.style.display = "block";
});

close_btn.addEventListener("click", () => {
  nav.forEach((nav_el) => nav_el.classList.remove("visible"));
  close_btn.style.display = "none";
  open_btn.style.display = "block";
});

let arrow = document.querySelectorAll(".arrow");
for (var i = 0; i < arrow.length; i++) {
  arrow[i].addEventListener("click", (e) => {
    let arrowParent = e.target.parentElement.parentElement;//selecting main parent of arrow
    arrowParent.classList.toggle("showMenu");
  });
}
let sidebar = document.querySelector(".sidebar");
let sidebarBtn = document.querySelector(".bx-menu");
console.log(sidebarBtn);
sidebarBtn.addEventListener("click", () => {
  sidebar.classList.toggle("close");
});