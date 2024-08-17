{
  description = "Pflotran flake";

  inputs.nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs =
    {
      self,
      nixpkgs,
      poetry2nix,
    }:
    let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
        config.allowUnfree = true;
      };

      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryEnv;
      python3_env = mkPoetryEnv { projectDir = ./.; };
    in
    {
      packages.x86_64-linux = rec {
        default = pflotran;

        hdf5 = pkgs.hdf5.override {
          cppSupport = false;
          fortranSupport = true;
          mpiSupport = true;
        };

        petsc =
          (pkgs.petsc.override {
            petsc-optimized = true;
            hdf5-support = true;
            inherit hdf5;
          }).overrideAttrs
            { patches = [ ./filter_mpi_warnings.patch ]; };

        pflotran = pkgs.stdenv.mkDerivation rec {
          name = "pflotran";
          version = "5.0.0";
          src = pkgs.fetchFromBitbucket {
            owner = "pflotran";
            repo = "pflotran";
            rev = "v${version}";
            hash = "sha256-j934pPT9zSbRgV4xgwJtycYcaq9Qs7Hgpxc5e6dKPdM=";
          };
          enableParallelBuilding = true;
          PETSC_DIR = petsc;
          nativeBuildInputs = [
            pkgs.mpi
            pkgs.pkg-config
          ];
          buildInputs = [ hdf5 ];
          patches = [ ./pflotran.patch ];
          doCheck = false;
        };

        inherit python3_env;
      };

      devShells.x86_64-linux = {
        default = pkgs.mkShell {
          PFLOTRAN_DIR = self.packages.x86_64-linux.default;
          buildInputs = [
            self.packages.x86_64-linux.default
            pkgs.mpi
            pkgs.poetry
            pkgs.nixfmt-rfc-style
            pkgs.treefmt
            python3_env
          ];
        };
      };

      checks.x86_64-linux = {
        treefmt = pkgs.stdenvNoCC.mkDerivation {
          name = "treefmtTest";
          src = ./.;

          doCheck = true;

          nativeBuildInputs = [
            pkgs.treefmt
            pkgs.nixfmt-rfc-style
            pkgs.ruff
          ];

          checkPhase = ''
            treefmt --version
            treefmt --verbose --on-unmatched=debug --no-cache --fail-on-change
          '';

          installPhase = "mkdir -p $out";
        };

        ruff = pkgs.stdenvNoCC.mkDerivation {
          name = "ruff";
          src = ./.;

          doCheck = true;

          nativeBuildInputs = [ pkgs.ruff ];

          checkPhase = ''
            ruff check .
          '';

          installPhase = "mkdir -p $out";
        };

        pyright = pkgs.stdenvNoCC.mkDerivation {
          name = "pyright";
          src = ./.;

          doCheck = true;

          nativeBuildInputs = [
            pkgs.pyright
            python3_env
          ];

          checkPhase = ''
            pyright .
          '';

          installPhase = "mkdir -p $out";
        };

        check_h5_file = pkgs.stdenvNoCC.mkDerivation {
          name = "checkH5File";
          src = ./.;

          doCheck = true;

          nativeBuildInputs = [
            self.packages.x86_64-linux.default
            pkgs.mpi
            pkgs.hdf5
            pkgs.openssh
            python3_env
          ];

          checkPhase = ''
            python -m vary_my_params --non-interactive
            # h5diff exits with code 0 if any objects are not comparable
            h5diff -v1 datasets_out/*/datapoint-0/pflotran.h5 tests/reference_files/pflotran.h5 | tee diff.out
            if grep -q "Some objects are not comparable" diff.out; then
              exit 1
            fi
          '';

          installPhase = "mkdir -p $out";
        };

        pytest = pkgs.stdenvNoCC.mkDerivation {
          name = "pytest";
          src = ./.;

          doCheck = true;

          nativeBuildInputs = [ python3_env ];

          checkPhase = ''
            pytest
          '';

          installPhase = "mkdir -p $out";
        };
      };
    };
}
