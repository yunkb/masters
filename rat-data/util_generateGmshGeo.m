function generateGmshGeo(output_filename,mesh_refinement_skull,mesh_refinement_tumor)
global x_skull y_skull x_tumor y_tumor
if(nargin == 1)
    mesh_refinement_skull = 1;
    mesh_refinement_tumor = 1;
end
fp=fopen(output_filename,'w');
fprintf(fp,['lc1 = ',num2str(mesh_refinement_skull),';\n']);
fprintf(fp,['lc2 = ',num2str(mesh_refinement_tumor),';\n']);
%print the nodes on the skull boundary
x = x_skull;
y = y_skull;
Np_skull = length(x);
for n=1:Np_skull
    fprintf(fp,['Point(',num2str(n),')={',num2str(x(n)),',',num2str(y(n)),',',num2str(0),',',num2str(mesh_refinement_skull),'};\n']);
end
%print line connections between the nodes (skull)
Line_count = Np_skull;
for n=1:Np_skull-1
    fprintf(fp,['Line(',num2str(n),')={',num2str(n),',',num2str(n+1),'};\n']);
end
fprintf(fp,['Line(',num2str(Np_skull),')={',num2str(Np_skull),',',num2str(1),'};\n']);
%print line loop
fprintf(fp,['Line Loop(',num2str(Np_skull+1),')={']);
for n=1:Np_skull-1
    fprintf(fp,[num2str(n),',']);
end
fprintf(fp,[num2str(Np_skull),'};\n']);
%print the nodes on the tumor boundary
x = x_tumor;
y = y_tumor;
Np_tumor = length(x);
for n=1:Np_tumor
    fprintf(fp,['Point(',num2str(Np_skull+n),')={',num2str(x(n)),',',num2str(y(n)),',',num2str(0),',',num2str(mesh_refinement_tumor),'};\n']);
end
%print line connections between the nodes (tumor)
for n=Np_skull+1:Np_skull+Np_tumor-1
    fprintf(fp,['Line(',num2str(n),')={',num2str(n),',',num2str(n+1),'};\n']);
end
fprintf(fp,['Line(',num2str(Np_skull+Np_tumor),')={',num2str(Np_skull+Np_tumor),',',num2str(Np_skull+1),'};\n']);
%print line loops that define the skull and tumor boundary
fprintf(fp,['Line Loop(',num2str(Np_skull+Np_tumor+1),')={']);
for n=Np_skull+1:Np_skull+Np_tumor-1
    fprintf(fp,[num2str(n),',']);
end
fprintf(fp,[num2str(Np_skull+Np_tumor),'};\n']);
%print the surface
fprintf(fp,['Plane Surface(',num2str(Np_skull+Np_tumor+2),')={',num2str(Np_skull+1),', -',num2str(Np_skull+Np_tumor+1),'};\n']);
fprintf(fp,['Plane Surface(',num2str(Np_skull+Np_tumor+3),')={',num2str(Np_skull+Np_tumor+1),'};\n']);
%print the surface
%name of the extra-tumor area (Surface 1)
%name of the tumor area (Surface 2)
%name of the skull area (Boundary 1)
%name of the tumor boundary (Boundary 2)
fprintf(fp,['Physical Surface("Surface 1")={',num2str(Np_skull+Np_tumor+2),'};\n']);
fprintf(fp,['Physical Surface("Surface 2")={',num2str(Np_skull+Np_tumor+3),'};\n']);
fprintf(fp,['Physical Line("Boundary 1")={']);
for n=1:Np_skull-1
    fprintf(fp,[num2str(n),',']);
end
fprintf(fp,[num2str(Np_skull),'};\n']);
fprintf(fp,['Physical Line("Boundary 2")={']);
for n=Np_skull+1:Np_skull+Np_tumor-1
    fprintf(fp,[num2str(n),',']);
end
fprintf(fp,[num2str(Np_skull+Np_tumor),'};\n']);
%fprintf(fp,'Mesh.CharacteristicLengthExtendFromBoundary = 10;\n');
%fprintf(fp,'Mesh.CharacteristicLengthFromPoints = 10;\n');
%fprintf(fp,'Mesh.CharacteristicLengthFromCurvature = 10;\n');
fclose all;
end