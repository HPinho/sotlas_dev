import { Link } from "react-router-dom";

const Logo = () => {
  return (
    <Link to="/" className="flex items-center gap-2.5 group select-none" aria-label="Sotlas — home">
      <div className="relative flex items-center justify-center w-9 h-9 transition-transform group-hover:rotate-6 duration-300 flex-shrink-0">
        <img
          src="/icone-sotlas.svg"
          alt=""
          className="relative z-10 w-full h-full object-contain"
        />
      </div>

      <span className="text-xl font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
        Sotlas
      </span>
    </Link>
  );
};

export default Logo;
