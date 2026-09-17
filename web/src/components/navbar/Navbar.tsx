import Logo from "./Logo";
import SearchBar from "./SearchBar";
import NavLinks from "./NavLinks";
import MobileMenu from "./MobileMenu";

const Navbar = () => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 w-full bg-background/90 backdrop-blur-xl border-b border-border/70 transition-colors duration-200">
      <nav className="flex items-center justify-between w-full max-w-7xl mx-auto px-4 md:px-8 py-3">
        {/* Left Section: Logo + SearchBar */}
        <div className="flex items-center gap-5">
          <Logo />
          <SearchBar />
        </div>

        {/* Right Section: NavLinks + MobileMenu */}
        <div className="flex items-center gap-2.5">
          <NavLinks />
          <MobileMenu />
        </div>
      </nav>
    </header>
  );
};

export default Navbar;
